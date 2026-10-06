"""Per-turn conservative admission budget, shared by planning and model/tool rounds."""
import json
import threading
from langchain_core.utils.function_calling import convert_to_openai_tool


class LLMBudgetExceeded(RuntimeError):
    pass


class BudgetedLLM:
    def __init__(self, llm, token_limit, *, state=None, tools=None, output_parameter=None):
        self._llm = llm
        self._state = state if state is not None else {'remaining': token_limit, 'lock': threading.Lock()}
        self._tools = tools or []
        self._output_parameter = output_parameter or (
            'max_output_tokens' if 'google_genai' in type(llm).__module__ else 'max_tokens'
        )

    def __getattr__(self, name):
        return getattr(self._llm, name)

    def bind_tools(self, tools):
        return BudgetedLLM(self._llm.bind_tools(tools), 0, state=self._state, tools=tools,
                           output_parameter=self._output_parameter)

    def _admit(self, messages):
        # Text-only chat: one token per UTF-8 byte plus framing is deliberately
        # conservative. Include tool schemas, previous calls, and message metadata.
        payload = [m.model_dump() if hasattr(m, 'model_dump') else m for m in messages]
        schemas = [convert_to_openai_tool(t) for t in self._tools]
        bound = len(json.dumps([payload, schemas], ensure_ascii=False, default=str).encode()) + 2048
        with self._state['lock']:
            output = min(4096, self._state['remaining'] - bound)
            if output < 256:
                raise LLMBudgetExceeded('This turn reached its token budget. Please shorten the request or start a new turn.')
            self._state['remaining'] -= bound + output
        return self._llm.bind(**{self._output_parameter: output})

    def invoke(self, messages, **kwargs):
        return self._admit(messages).invoke(messages, **kwargs)

    def stream(self, messages, **kwargs):
        yield from self._admit(messages).stream(messages, **kwargs)
