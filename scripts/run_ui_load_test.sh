#!/bin/bash
# Helper script to run UI load tests with common configurations

# Default values
USERS=5
DURATION=120
URL="http://localhost:4173"
HEADLESS="true"
EMAIL=""
PASSWORD=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --users)
            USERS="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --url)
            URL="$2"
            shift 2
            ;;
        --headless)
            HEADLESS="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --password)
            PASSWORD="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./scripts/run_ui_load_test.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --users NUM        Number of concurrent users (default: 5)"
            echo "  --duration SEC     Test duration in seconds (default: 120)"
            echo "  --url URL          Base URL (default: http://localhost:4173)"
            echo "  --headless BOOL    Run headless true/false (default: true)"
            echo "  --email EMAIL      Email for authenticated tests"
            echo "  --password PASS    Password for authenticated tests"
            echo "  --help             Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/run_ui_load_test.sh --users 10 --duration 300"
            echo "  ./scripts/run_ui_load_test.sh --users 1 --headless false"
            echo "  ./scripts/run_ui_load_test.sh --users 5 --email test@example.com --password pass123"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build the command
CMD="python scripts/ui_load_test.py --users $USERS --duration $DURATION --url $URL --headless $HEADLESS"

if [ -n "$EMAIL" ]; then
    CMD="$CMD --email $EMAIL"
fi

if [ -n "$PASSWORD" ]; then
    CMD="$CMD --password $PASSWORD"
fi

echo "Running UI Load Test..."
echo "Users: $USERS | Duration: ${DURATION}s | URL: $URL | Headless: $HEADLESS"
echo ""

# Run the test
eval $CMD

# Made with Bob
