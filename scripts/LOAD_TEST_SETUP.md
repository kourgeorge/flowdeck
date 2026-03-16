# Load Testing Setup Guide

## ⚠️ Important: Start Your Services First!

Before running load tests, you **MUST** have both frontend and backend services running.

## Quick Setup

### 1. Start Backend (Terminal 1)

```bash
cd backend
python run.py
```

The backend should start on **http://localhost:8002**

### 2. Start Frontend (Terminal 2)

**Option A: Production Build (Recommended for load testing)**
```bash
cd frontend
npm run build
npm run preview
```
This starts the frontend on **http://localhost:4173**

**Option B: Development Server**
```bash
cd frontend
npm run dev
```
This starts the frontend on **http://localhost:5173**

### 3. Run Load Tests (Terminal 3)

**For production build (port 4173):**
```bash
# Default - no URL needed
python scripts/ui_load_test.py --users 10 --duration 300

# Or use helper script
./scripts/run_ui_load_test.sh --users 10 --duration 300
```

**For dev server (port 5173):**
```bash
python scripts/ui_load_test.py --users 10 --duration 300 --url http://localhost:5173
```

## Verify Services Are Running

Before running tests, check that services are accessible:

```bash
# Check backend
curl http://localhost:8002/health || echo "Backend not running!"

# Check frontend (production)
curl http://localhost:4173 || echo "Frontend not running on 4173!"

# Check frontend (dev)
curl http://localhost:5173 || echo "Frontend not running on 5173!"
```

## Common Issues

### "ERR_CONNECTION_REFUSED"

**Problem**: Frontend or backend not running

**Solution**: 
1. Check if services are running (see above)
2. Start the missing service
3. Wait a few seconds for services to fully start
4. Run the test again

### "Timeout waiting for selector"

**Problem**: Page loads but UI elements not found

**Solution**:
1. Open the URL in your browser manually
2. Verify the page loads correctly
3. Check if you need to be logged in
4. Run test with `--headless false` to see what's happening

### Wrong Port

**Problem**: Test tries to connect to wrong port

**Solution**: Use `--url` parameter:
```bash
python scripts/ui_load_test.py --users 5 --duration 120 --url http://localhost:YOUR_PORT
```

## Complete Example Workflow

```bash
# Terminal 1: Start backend
cd /Users/georgekour/repositories/flowdeck/backend
python run.py

# Terminal 2: Start frontend (production build)
cd /Users/georgekour/repositories/flowdeck/frontend
npm run build && npm run preview

# Terminal 3: Wait 10 seconds, then run test
cd /Users/georgekour/repositories/flowdeck
sleep 10
python scripts/ui_load_test.py --users 5 --duration 120
```

## Production vs Development

| Aspect | Production Build | Development Server |
|--------|-----------------|-------------------|
| **Port** | 4173 | 5173 |
| **Command** | `npm run preview` | `npm run dev` |
| **Speed** | Faster | Slower (HMR overhead) |
| **Best for** | Load testing | Development |
| **Build required** | Yes (`npm run build`) | No |

**Recommendation**: Use production build (port 4173) for load testing as it's closer to real-world performance.

## Test Scenarios

### Scenario 1: Quick Smoke Test
```bash
# 1 user, 30 seconds, visible browser
python scripts/ui_load_test.py --users 1 --duration 30 --headless false
```

### Scenario 2: Light Load
```bash
# 5 users, 2 minutes
./scripts/run_ui_load_test.sh --users 5 --duration 120
```

### Scenario 3: Medium Load
```bash
# 10 users, 5 minutes
./scripts/run_ui_load_test.sh --users 10 --duration 300
```

### Scenario 4: Heavy Load
```bash
# 20 users, 10 minutes
./scripts/run_ui_load_test.sh --users 20 --duration 600
```

### Scenario 5: Authenticated Users
```bash
# 5 users with login
./scripts/run_ui_load_test.sh --users 5 --duration 180 \
  --email test@example.com --password yourpassword
```

## Monitoring During Tests

While tests run, monitor:

1. **Backend logs** - Check for errors
2. **CPU/Memory** - Use `top` or Activity Monitor
3. **Network** - Check response times
4. **Browser DevTools** - If running with `--headless false`

## Next Steps

1. ✅ Start backend and frontend
2. ✅ Verify services are accessible
3. ✅ Run a quick smoke test (1 user)
4. ✅ Gradually increase load
5. ✅ Monitor and optimize bottlenecks

Happy testing! 🚀