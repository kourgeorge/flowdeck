"""Compatibility stub: host Python execution is disabled until OS isolation exists."""
from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec


class ExecutePythonTool(BaseTool):
    enabled = False
    spec = ToolSpec(
        name="execute_python", version="2.0",
        description="Python execution is unavailable.",
        input_schema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    )

    def execute(self, ctx: ExecutionContext, *, code: str, **_) -> ToolResult:
        return ToolResult(ok=False, error={"code": "TOOL_DISABLED", "message": "Python execution is unavailable."})


def _run_sandboxed(code: str) -> str:
    return "[TOOL_DISABLED] Python execution is unavailable."
