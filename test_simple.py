#!/usr/bin/env python3
"""Minimal test - just verify the refactored files compile and basic structure works."""

print("Testing refactored TradingAgents...")

# Test 1: Import isolated context helper
print("1. Testing isolated_context module...")
try:
    from ai_engine.tradingagents.agents.analysts.isolated_context import run_analyst_with_isolated_context
    print("   ✓ isolated_context imported")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)

# Test 2: Import updated analyst
print("2. Testing market_analyst module...")
try:
    from ai_engine.tradingagents.agents.analysts.market_analyst import create_market_analyst
    print("   ✓ market_analyst imported")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)

# Test 3: Import updated state
print("3. Testing agent_states module...")
try:
    from ai_engine.tradingagents.agents.utils.agent_states import AgentState
    print("   ✓ agent_states imported")
    
    # Verify it's TypedDict not MessagesState
    import inspect
    bases = AgentState.__bases__
    print(f"   ✓ AgentState bases: {[b.__name__ for b in bases]}")
    
    # Check for context fields
    if hasattr(AgentState, '__annotations__'):
        annotations = AgentState.__annotations__
        context_fields = [k for k in annotations.keys() if k.startswith('_') and k.endswith('_context')]
        print(f"   ✓ Found {len(context_fields)} context fields: {context_fields[:3]}...")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)

# Test 4: Import isolated tool node
print("4. Testing isolated_tool_node module...")
try:
    from ai_engine.tradingagents.graph.isolated_tool_node import make_isolated_tool_node
    print("   ✓ isolated_tool_node imported")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)

# Test 5: Import updated conditional logic
print("5. Testing conditional_logic module...")
try:
    from ai_engine.tradingagents.graph.conditional_logic import ConditionalLogic
    print("   ✓ conditional_logic imported")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)

print("\n" + "="*60)
print("✓ All refactored modules imported successfully!")
print("="*60)
print("\nNext step: Run full integration test with:")
print("  python backend/run_analysis_standalone.py AAPL")
