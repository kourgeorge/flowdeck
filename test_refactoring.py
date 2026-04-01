#!/usr/bin/env python3
"""
Quick test script to verify the refactoring works.
Tests the isolated tool node without full graph initialization.
"""

import sys
sys.path.insert(0, '.')

from langchain_core.messages import AIMessage, ToolMessage

# Test 1: Verify isolated_tool_node module loads
print("Test 1: Loading isolated_tool_node...")
from ai_engine.tradingagents.graph.isolated_tool_node import make_isolated_tool_node
print("✓ isolated_tool_node loaded")

# Test 2: Create a mock tool
print("\nTest 2: Creating mock tool...")
def mock_tool(symbol: str) -> str:
    return f"Mock data for {symbol}"

mock_tool.name = "mock_tool"
print("✓ Mock tool created")

# Test 3: Create isolated tool node
print("\nTest 3: Creating isolated tool node...")
tool_node = make_isolated_tool_node([mock_tool], "_test_context")
print("✓ Isolated tool node created")

# Test 4: Test tool execution
print("\nTest 4: Testing tool execution...")
test_state = {
    "_test_context": [
        AIMessage(
            content="",
            tool_calls=[{
                "id": "test_call_1",
                "name": "mock_tool",
                "args": {"symbol": "AAPL"}
            }]
        )
    ]
}

result = tool_node(test_state)
print(f"✓ Tool executed, result keys: {list(result.keys())}")

# Verify result structure
if "_test_context" in result:
    messages = result["_test_context"]
    print(f"✓ Context updated with {len(messages)} messages")
    
    # Check for ToolMessage
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    if tool_messages:
        print(f"✓ Found {len(tool_messages)} ToolMessage(s)")
        print(f"  Content: {tool_messages[0].content}")
    else:
        print("✗ No ToolMessage found!")
        sys.exit(1)
else:
    print("✗ No _test_context in result!")
    sys.exit(1)

print("\n" + "="*50)
print("All tests passed! ✓")
print("="*50)
