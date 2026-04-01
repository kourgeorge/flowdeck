#!/usr/bin/env python3
"""Test that the refactored graph can be constructed without errors."""

import sys
import os

# Set minimal env vars to avoid credential errors
os.environ.setdefault('AZURE_OPENAI_ENDPOINT', 'https://dummy.openai.azure.com/')
os.environ.setdefault('AZURE_OPENAI_API_KEY', 'dummy-key-for-testing')
os.environ.setdefault('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
os.environ.setdefault('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
os.environ.setdefault('INFO_SERVICE_URL', 'http://localhost:8000')

print("Testing graph construction with refactored code...")

try:
    from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
    print("✓ TradingAgentsGraph imported")
    
    # Try to construct the graph
    config = {
        'llm_provider': 'azure',
        'deep_thinker': 'azure/gpt-4',
        'shallow_thinker': 'azure/gpt-4',
        'backend_url': 'http://localhost:8000',
        'info_service_url': 'http://localhost:8000',
    }
    
    print("✓ Constructing graph with market analyst only...")
    graph = TradingAgentsGraph(
        selected_analysts=['market'],
        config=config,
        debug=True
    )
    print("✓ Graph constructed successfully!")
    
    # Check that the graph has the expected structure
    if hasattr(graph, 'graph'):
        print("✓ Graph object has 'graph' attribute")
        nodes = list(graph.graph.nodes.keys()) if hasattr(graph.graph, 'nodes') else []
        print(f"✓ Graph has {len(nodes)} nodes")
        print(f"  Nodes: {nodes[:10]}...")  # Show first 10
    
    print("\n" + "="*60)
    print("✅ SUCCESS: Refactored graph construction works!")
    print("="*60)
    
except Exception as e:
    print(f"\n❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
