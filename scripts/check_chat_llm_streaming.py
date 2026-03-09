#!/usr/bin/env python3
"""
Check whether the chat LLM (same config as the backend chat) supports streaming.

Run from repo root (loads backend/.env automatically):
  python scripts/check_chat_llm_streaming.py
"""

from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
backend = repo_root / "backend"
if backend.is_dir():
    try:
        from dotenv import load_dotenv
        load_dotenv(backend / ".env")
        load_dotenv(repo_root / ".env")
    except ImportError:
        pass

def main():
    from ai_engine.llm_provider import get_config_from_env, get_llm

    config = get_config_from_env()
    provider = config.get("llm_provider") or "openai"
    model = config.get("deep_think_llm") or "gpt-4o"

    print("Chat LLM config (same as backend chat):")
    print(f"  Provider: {provider}")
    print(f"  Model (deep): {model}")
    print()

    llm = get_llm("deep", config, request_timeout=60)
    has_stream = hasattr(llm, "stream") and callable(getattr(llm, "stream", None))
    print(f"  Has .stream() method: {has_stream}")

    if not has_stream:
        print("\nStreaming is not available on this model instance.")
        return

    # Minimal stream test: one message, show what we extract per chunk (same logic as graph)
    from langchain_core.messages import HumanMessage

    def stream_chunk_delta(chunk):
        raw = getattr(chunk, "content", None)
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            return "".join(
                (b.get("text", "") if isinstance(b, dict) else str(b)) for b in raw
            )
        if raw is not None:
            return str(raw)
        kwargs = getattr(chunk, "additional_kwargs", None) or {}
        for key in ("content", "text", "reasoning", "delta"):
            if key in kwargs and isinstance(kwargs[key], str):
                return kwargs[key]
        return ""

    print("\nRunning a minimal stream test (one short prompt)...")
    try:
        deltas = []
        total_chunks = 0
        for chunk in llm.stream([HumanMessage(content="Say exactly: OK")]):
            total_chunks += 1
            d = stream_chunk_delta(chunk)
            if d:
                deltas.append(d)
            if len(deltas) >= 10:
                break
        if deltas:
            content = "".join(deltas)
            print(f"  Stream test: OK (got {len(deltas)} non-empty delta(s), content: {repr(content[:120])})")
        else:
            print(f"  Stream test: {total_chunks} chunk(s) received but all had empty content.")
            print("  If the model streams content in later chunks, the chat UI will still show them.")
    except Exception as e:
        print(f"  Stream test: FAILED — {e}")
        print("  Chat will fall back to non-streaming (one chunk per turn).")

if __name__ == "__main__":
    main()
