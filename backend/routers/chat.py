"""
Chat router: POST /api/chat  and  POST /api/chat/stream

Authenticated endpoints that run a stock market analyst ReAct agent.
Deducts tokens from the user's balance based on the number of agent trajectory steps.
"""

import asyncio
import json
import logging
from typing import AsyncIterator, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services import token_service
from services.chat_service import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


class ChatMessageIn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessageIn]


class ChatResponse(BaseModel):
    reply: str
    tokens_used: int
    balance: int


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run a chat turn with the stock market analyst agent.

    - Requires authentication (Bearer token).
    - Deducts tokens based on agent trajectory length (tool calls + LLM steps).
    - Minimum cost: 1 token per message.
    - Returns 402 if the user has insufficient token balance.
    """
    # Check user has at least 1 token
    balance = token_service.get_balance(current_user.id, db)
    if balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance. Please purchase more tokens to continue chatting.",
        )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    user_id = current_user.id

    # Run the agent in a thread pool (blocking LangChain calls)
    try:
        service = get_chat_service()
        result = await asyncio.to_thread(service.chat, messages, user_id, db)
    except Exception as e:
        logger.exception("Chat agent failed for user_id=%s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat agent error: {str(e)}",
        )

    reply = result.get("reply", "")
    tokens_used = result.get("tokens_used", 1)

    # Deduct tokens (best-effort; don't fail the response if deduction fails)
    try:
        token_service.deduct_for_chat(current_user.id, tokens_used, db)
    except Exception as e:
        logger.warning("Failed to deduct tokens for user_id=%s: %s", current_user.id, e)

    new_balance = token_service.get_balance(current_user.id, db)

    return ChatResponse(reply=reply, tokens_used=tokens_used, balance=new_balance)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream a chat turn as Server-Sent Events (SSE).

    Each SSE event is a JSON object:
      - ``{"type":"token","content":"..."}``  — incremental text chunk
      - ``{"type":"done","tokens_used":N}``   — stream finished; tokens deducted
      - ``{"type":"error","content":"..."}``  — error occurred

    - Requires authentication (Bearer token).
    - Returns 402 if the user has insufficient token balance.
    """
    balance = token_service.get_balance(current_user.id, db)
    if balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance. Please purchase more tokens to continue chatting.",
        )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    user_id = current_user.id

    async def event_generator() -> AsyncIterator[str]:
        service = get_chat_service()
        tokens_used = 1
        try:
            # Run the blocking generator in a thread and yield chunks as they arrive
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def run_generator():
                try:
                    for chunk in service.chat_stream(messages, user_id=user_id, db=db):
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
                except Exception as exc:
                    err_event = f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
                    loop.call_soon_threadsafe(queue.put_nowait, err_event)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            thread_task = asyncio.get_event_loop().run_in_executor(None, run_generator)

            while True:
                item = await queue.get()
                if item is None:
                    break
                # Parse tokens_used from done event, deduct immediately, then send updated balance
                if '"type":"done"' in item or '"type": "done"' in item:
                    try:
                        payload = json.loads(item.removeprefix("data: ").strip())
                        tokens_used = payload.get("tokens_used", 1)
                        # Deduct tokens now so the balance we send is post-deduction
                        try:
                            token_service.deduct_for_chat(user_id, tokens_used, db)
                        except Exception as deduct_err:
                            logger.warning("Failed to deduct tokens for user_id=%s: %s", user_id, deduct_err)
                        # Send the updated (post-deduction) balance to the client
                        new_balance = token_service.get_balance(user_id, db)
                        payload["balance"] = new_balance
                        yield f"data: {json.dumps(payload)}\n\n"
                        tokens_used = 0  # mark as already deducted
                        continue
                    except Exception:
                        pass
                yield item

            await thread_task

        except Exception as e:
            logger.exception("Chat stream failed for user_id=%s: %s", user_id, e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            # Deduct tokens only if not already deducted in the done-event handler
            if tokens_used > 0:
                try:
                    token_service.deduct_for_chat(user_id, tokens_used, db)
                except Exception as e:
                    logger.warning("Failed to deduct tokens for user_id=%s: %s", user_id, e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )

# Made with Bob
