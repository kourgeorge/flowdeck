#!/bin/bash
# Check if required services are running for load testing

echo "🔍 Checking Flowdeck Services..."
echo ""

# Check backend
echo "Backend (port 8002):"
if curl -s http://localhost:8002/health > /dev/null 2>&1; then
    echo "  ✅ Backend is running on http://localhost:8002"
else
    echo "  ❌ Backend is NOT running"
    echo "     Start with: cd backend && python run.py"
fi
echo ""

# Check frontend on common ports
echo "Frontend:"
FRONTEND_RUNNING=false

if curl -s http://localhost:4173 > /dev/null 2>&1; then
    echo "  ✅ Frontend is running on http://localhost:4173 (production)"
    FRONTEND_RUNNING=true
    FRONTEND_PORT=4173
fi

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "  ✅ Frontend is running on http://localhost:5173 (dev)"
    FRONTEND_RUNNING=true
    FRONTEND_PORT=5173
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "  ✅ Frontend is running on http://localhost:3000"
    FRONTEND_RUNNING=true
    FRONTEND_PORT=3000
fi

if [ "$FRONTEND_RUNNING" = false ]; then
    echo "  ❌ Frontend is NOT running on any common port (3000, 4173, 5173)"
    echo "     Start with:"
    echo "       Production: cd frontend && npm run build && npm run preview"
    echo "       Dev:        cd frontend && npm run dev"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FRONTEND_RUNNING" = true ]; then
    echo "✅ Ready for load testing!"
    echo ""
    echo "Run UI load test with:"
    echo "  python scripts/ui_load_test.py --users 5 --duration 120 --url http://localhost:$FRONTEND_PORT"
    echo ""
    echo "Or use the helper script:"
    echo "  ./scripts/run_ui_load_test.sh --users 5 --duration 120"
else
    echo "⚠️  Please start the frontend server first!"
    echo ""
    echo "Quick start:"
    echo "  Terminal 1: cd backend && python run.py"
    echo "  Terminal 2: cd frontend && npm run build && npm run preview"
    echo "  Terminal 3: python scripts/ui_load_test.py --users 5 --duration 120"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Made with Bob
