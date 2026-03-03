"""
ExecutePythonTool — run Python code in a sandboxed subprocess.

Safety measures (identical to the original chat_service implementation):
  1. Static pattern scan — blocks dangerous imports/builtins before execution.
  2. Code length cap — rejects snippets over 16 KB.
  3. subprocess with shell=False — no shell injection.
  4. Stripped environment — no credentials or PATH tricks.
  5. Isolated /tmp working directory.
  6. Hard 10-second wall-clock timeout.
  7. Memory cap via resource.setrlimit (128 MB RSS, Unix only).
  8. stdout/stderr capped at 8 KB.
"""

from __future__ import annotations

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# Allowlist / blocklist (mirrors chat_service.py)
# ---------------------------------------------------------------------------

_ALLOWED_MODULES = frozenset({
    "math", "cmath", "decimal", "fractions", "statistics", "random",
    "collections", "heapq", "bisect", "array", "queue", "itertools",
    "functools", "operator", "copy", "pprint",
    "string", "re", "textwrap", "unicodedata", "difflib",
    "datetime", "calendar", "time",
    "json", "csv", "base64", "hashlib", "hmac", "struct",
    "numpy", "pandas", "scipy", "sklearn", "statsmodels",
    "typing", "dataclasses", "enum", "abc",
    "io",
})

_BLOCKED_PATTERNS = [
    "import os", "import sys", "import subprocess", "import socket",
    "import requests", "import urllib", "import http", "import ftplib",
    "import smtplib", "import shutil", "import pathlib", "import glob",
    "import tempfile", "import pickle", "import shelve", "import sqlite3",
    "import ctypes", "import cffi", "import multiprocessing", "import threading",
    "import concurrent", "import asyncio",
    "__import__", "open(", "exec(", "eval(", "compile(",
    "globals(", "locals(", "vars(", "getattr(", "setattr(", "delattr(",
    "breakpoint(", "__builtins__", "__class__", "__subclasses__", "builtins",
]

# ---------------------------------------------------------------------------
# ToolSpec
# ---------------------------------------------------------------------------

_EXECUTE_PYTHON_SPEC = ToolSpec(
    name="execute_python",
    version="1.0",
    description=(
        "Execute a Python code snippet in a secure sandbox and return the printed output. "
        "Use this tool for: mathematical calculations, statistical analysis, financial modelling, "
        "data transformations, sorting/filtering lists of numbers, computing returns or ratios, "
        "or any task where running code produces a more accurate answer than reasoning alone. "
        "Allowed modules: math, statistics, random, collections, itertools, functools, datetime, "
        "json, csv, decimal, fractions, re, string, numpy, pandas, scipy. "
        "NOT allowed: file I/O, network access, os/sys/subprocess, pickle, threading, or any "
        "module not in the allowlist. Keep code under 16 KB. Use print() to produce output. "
        "When working with data from get_multi_historical_prices, parse the JSON using the json module. "
        "To produce a chart, print a line starting with CHART_JSON: followed by the chart spec JSON. "
        "IMPORTANT: When creating charts, ALWAYS adapt the Y-axis by calculating appropriate min/max "
        "values from the data and including yAxisConfig in the chart spec (e.g., add 5-10% padding "
        "above/below the data range for visual clarity)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Valid Python 3 code to execute. Must use print() to produce output. "
                    "Example: 'import math\\nprint(math.sqrt(144))'"
                ),
            }
        },
        "required": ["code"],
    },
    side_effects=False,
    tags=["code", "python", "compute"],
)


class ExecutePythonTool(BaseTool):
    spec = _EXECUTE_PYTHON_SPEC

    def execute(self, ctx: ExecutionContext, *, code: str, **_) -> ToolResult:
        try:
            result = _run_sandboxed(code)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# Sandbox implementation
# ---------------------------------------------------------------------------

def _run_sandboxed(code: str) -> str:
    import subprocess
    import sys
    import textwrap
    import tempfile
    import os as _os

    # 1. Length cap
    MAX_CODE_BYTES = 16384
    if len(code.encode()) > MAX_CODE_BYTES:
        return (
            f"Error: code exceeds the {MAX_CODE_BYTES}-byte limit "
            f"({len(code.encode())} bytes submitted)."
        )

    # 2. Static pattern scan
    code_lower = code.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in code_lower:
            return (
                f"Error: code contains a blocked pattern: `{pattern}`. "
                "Only safe standard-library and data-science modules are permitted."
            )

    # 3. Build wrapper script
    wrapper = textwrap.dedent(f"""\
        import resource, sys

        try:
            resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 256 * 1024 * 1024))
        except Exception:
            pass

        _ALLOWED = {{
            'math', 'cmath', 'decimal', 'fractions', 'statistics', 'random',
            'collections', 'heapq', 'bisect', 'array', 'queue', 'itertools',
            'functools', 'operator', 'copy', 'pprint',
            'string', 're', 'textwrap', 'unicodedata', 'difflib',
            'datetime', 'calendar', 'time',
            'json', 'csv', 'base64', 'hashlib', 'hmac', 'struct',
            'numpy', 'pandas', 'scipy', 'sklearn', 'statsmodels',
            'typing', 'dataclasses', 'enum', 'abc', 'io',
        }}

        import builtins as _builtins_mod
        _real_open = _builtins_mod.open
        
        # Mock open to prevent pandas from accessing macOS system files
        def _safe_open(file, *args, **kwargs):
            file_str = str(file)
            # Block access to macOS system files that pandas tries to read
            if '/System/Library/CoreServices/SystemVersion.plist' in file_str:
                raise PermissionError(f"Access to system files is not allowed: {{file_str}}")
            # Block any absolute paths outside /tmp
            if file_str.startswith('/') and not file_str.startswith('/tmp'):
                raise PermissionError(f"Access to files outside /tmp is not allowed: {{file_str}}")
            return _real_open(file, *args, **kwargs)
        
        _builtins_mod.open = _safe_open
        
        _real_import = _builtins_mod.__import__
        def _safe_import(name, *args, **kwargs):
            top = name.split('.')[0]
            if top not in _ALLOWED:
                raise ImportError(f"Module '{{name}}' is not allowed in the sandbox.")
            return _real_import(name, *args, **kwargs)

        _SAFE_BUILTINS = {{
            k: v for k, v in _builtins_mod.__dict__.items()
            if k in {{
                'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
                'sorted', 'reversed', 'sum', 'min', 'max', 'abs', 'round',
                'int', 'float', 'str', 'bool', 'list', 'dict', 'set', 'tuple',
                'type', 'isinstance', 'issubclass', 'hasattr',
                'repr', 'format', 'chr', 'ord', 'hex', 'oct', 'bin',
                'divmod', 'pow', 'hash', 'id', 'iter', 'next', 'callable',
                'all', 'any', 'staticmethod', 'classmethod', 'property',
                'NotImplemented', 'Ellipsis', 'None', 'True', 'False',
                '__name__', '__doc__', '__spec__', '__loader__', '__package__',
                'Exception', 'ValueError', 'TypeError', 'KeyError',
                'IndexError', 'AttributeError', 'RuntimeError',
                'StopIteration', 'ZeroDivisionError', 'OverflowError',
                'ArithmeticError', 'LookupError', 'AssertionError',
                'NotImplementedError', 'ImportError', 'NameError',
            }}
        }}
        _SAFE_BUILTINS['__import__'] = _safe_import
        _SAFE_BUILTINS['open'] = None

        _user_code = {repr(code)}
        exec(compile(_user_code, '<sandbox>', 'exec'), {{'__builtins__': _SAFE_BUILTINS}})
    """)

    # 4. Write wrapper to temp file
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as tf:
            tf.write(wrapper)
            tmp_path = tf.name
    except Exception as e:
        return f"Error: could not create sandbox script: {e}"

    # 5. Stripped environment
    safe_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "LANG": "en_US.UTF-8",
        "PYTHONPATH": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        # Prevent pandas from accessing macOS system files
        "_PYTHON_HOST_PLATFORM": "linux-x86_64",
        "SYSTEM_VERSION_COMPAT": "0",
    }

    # 6. Execute
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/tmp",
            env=safe_env,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return "Error: code execution timed out (10-second limit)."
    except Exception as e:
        return f"Error: sandbox execution failed: {e}"
    finally:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass

    # 7. Cap output size
    MAX_OUTPUT = 8192
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if len(stdout) > MAX_OUTPUT:
        stdout = stdout[:MAX_OUTPUT] + "\n... [output truncated]"
    if len(stderr) > MAX_OUTPUT:
        stderr = stderr[:MAX_OUTPUT] + "\n... [stderr truncated]"

    output = stdout
    if stderr:
        output += f"\n[stderr]:\n{stderr}"

    return output.strip() or "(no output)"

# Made with Bob
