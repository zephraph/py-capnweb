#!/bin/bash
# Comprehensive interop test runner for Cap'n Web
# Tests all combinations: PY→PY, PY→TS, TS→PY, TS→TS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Logging function
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if a port is in use
wait_for_port() {
    local port=$1
    local max_wait=10
    local count=0

    while ! nc -z 127.0.0.1 $port 2>/dev/null; do
        sleep 0.5
        count=$((count + 1))
        if [ $count -gt $((max_wait * 2)) ]; then
            return 1
        fi
    done
    return 0
}

# Kill process on port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "python3 not found. Please install Python 3.10+"
        exit 1
    fi

    # Check if capnweb is installed
    if ! python3 -c "import capnweb" 2>/dev/null; then
        error "capnweb module not found. Please install: pip install -e ."
        exit 1
    fi

    # Check Node.js for TypeScript tests
    if command -v node &> /dev/null; then
        log "Node.js found: $(node --version)"
        TS_AVAILABLE=true

        # Check if TypeScript dependencies are installed
        if [ -d "typescript/node_modules" ]; then
            log "TypeScript dependencies installed"
        else
            warning "TypeScript dependencies not installed. Run: cd typescript && npm install"
            TS_AVAILABLE=false
        fi
    else
        warning "Node.js not found. Skipping TypeScript tests."
        TS_AVAILABLE=false
    fi

    success "Dependency check complete"
    echo
}

# Run a single test scenario
run_test() {
    local server_lang=$1
    local client_lang=$2
    local server_port=$3

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log "═══════════════════════════════════════════════════════════"
    log "Test: ${server_lang} Server ← ${client_lang} Client"
    log "═══════════════════════════════════════════════════════════"

    # Clean up port
    kill_port $server_port

    # Start server
    local server_pid
    if [ "$server_lang" = "Python" ]; then
        log "Starting Python server on port $server_port..."
        python3 python/server.py $server_port > /tmp/server_${server_port}.log 2>&1 &
        server_pid=$!
    else
        log "Starting TypeScript server on port $server_port..."
        cd typescript
        npm run server $server_port > /tmp/server_${server_port}.log 2>&1 &
        server_pid=$!
        cd ..
    fi

    # Wait for server to start
    log "Waiting for server to start..."
    if wait_for_port $server_port; then
        success "Server started (PID: $server_pid)"
    else
        error "Server failed to start"
        kill $server_pid 2>/dev/null || true
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo
        return 1
    fi

    sleep 1

    # Run client
    local client_result=0
    if [ "$client_lang" = "Python" ]; then
        log "Running Python client..."
        if python3 python/client.py "http://127.0.0.1:$server_port/rpc/batch" > /tmp/client_${server_port}.log 2>&1; then
            success "Client tests passed"
        else
            error "Client tests failed"
            client_result=1
        fi
    else
        log "Running TypeScript client..."
        cd typescript
        if npm run client "http://127.0.0.1:$server_port/rpc/batch" > /tmp/client_${server_port}.log 2>&1; then
            success "Client tests passed"
            client_result=0
        else
            error "Client tests failed"
            client_result=1
        fi
        cd ..
    fi

    # Show output on failure
    if [ $client_result -ne 0 ]; then
        warning "Client output:"
        cat /tmp/client_${server_port}.log
        warning "Server output:"
        cat /tmp/server_${server_port}.log
    fi

    # Stop server
    log "Stopping server (PID: $server_pid)..."
    kill $server_pid 2>/dev/null || true
    wait $server_pid 2>/dev/null || true

    # Clean up port
    kill_port $server_port

    if [ $client_result -eq 0 ]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        success "✓ Test passed: ${server_lang} ← ${client_lang}"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        error "✗ Test failed: ${server_lang} ← ${client_lang}"
    fi

    echo
    return $client_result
}

# Main test execution
main() {
    echo
    log "═══════════════════════════════════════════════════════════"
    log "Cap'n Web Interoperability Test Suite"
    log "═══════════════════════════════════════════════════════════"
    echo

    check_dependencies

    # Test 1: Python Server ← Python Client
    run_test "Python" "Python" 18080

    if [ "$TS_AVAILABLE" = true ]; then
        # Test 2: Python Server ← TypeScript Client
        run_test "Python" "TypeScript" 18081

        # Test 3: TypeScript Server ← Python Client
        run_test "TypeScript" "Python" 18082

        # Test 4: TypeScript Server ← TypeScript Client
        run_test "TypeScript" "TypeScript" 18083
    else
        warning "Skipping TypeScript tests (Node.js not available or dependencies not installed)"
    fi

    # Final summary
    echo
    log "═══════════════════════════════════════════════════════════"
    log "Test Summary"
    log "═══════════════════════════════════════════════════════════"
    echo "  Total:  $TOTAL_TESTS"
    echo "  Passed: $PASSED_TESTS"
    echo "  Failed: $FAILED_TESTS"
    echo

    if [ $FAILED_TESTS -eq 0 ]; then
        success "✓ All interop tests passed!"
        exit 0
    else
        error "✗ Some tests failed"
        exit 1
    fi
}

# Run main function
main "$@"
