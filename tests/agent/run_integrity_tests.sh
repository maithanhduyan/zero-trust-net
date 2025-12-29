#!/bin/bash
# tests/agent/run_integrity_tests.sh
# =====================================================
# Zero Trust Agent Integrity Test Runner
# =====================================================
#
# Usage:
#   ./run_integrity_tests.sh              # Run all tests
#   ./run_integrity_tests.sh unit         # Unit tests only
#   ./run_integrity_tests.sh service      # Service tests only
#   ./run_integrity_tests.sh integration  # Integration tests (requires server)
#   ./run_integrity_tests.sh coverage     # Run with coverage report
#   ./run_integrity_tests.sh watch        # Watch mode (rerun on file change)
#
# Environment Variables:
#   CONTROL_PLANE_URL - URL of control plane (default: http://localhost:8000)
#   ADMIN_TOKEN       - Admin token for API tests
#   VERBOSE           - Set to 1 for verbose output

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TESTS_DIR="$SCRIPT_DIR"

# Configuration
CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://localhost:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-test-admin-token}"
VERBOSE="${VERBOSE:-0}"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    if ! command -v python3 &> /dev/null; then
        log_fail "python3 is required"
        exit 1
    fi

    if ! python3 -c "import pytest" &> /dev/null; then
        log_warn "pytest not found, installing..."
        pip install pytest pytest-cov pytest-asyncio
    fi

    log_pass "Dependencies OK"
}

# Setup Python path
setup_python_path() {
    export PYTHONPATH="$PROJECT_ROOT/agent:$PROJECT_ROOT/control-plane:$PYTHONPATH"
}

# Run unit tests for agent integrity module
run_unit_tests() {
    print_header "Unit Tests - Agent Integrity Module"

    cd "$PROJECT_ROOT"

    PYTEST_ARGS="-v"
    [[ "$VERBOSE" == "1" ]] && PYTEST_ARGS="-v -s"

    python3 -m pytest "$TESTS_DIR/test_agent_integrity.py" $PYTEST_ARGS \
        --tb=short \
        -x  # Stop on first failure

    log_pass "Unit tests completed"
}

# Run service tests for control plane integrity service
run_service_tests() {
    print_header "Service Tests - Control Plane Integrity Service"

    cd "$PROJECT_ROOT"

    PYTEST_ARGS="-v"
    [[ "$VERBOSE" == "1" ]] && PYTEST_ARGS="-v -s"

    python3 -m pytest "$TESTS_DIR/test_integrity_service.py" $PYTEST_ARGS \
        --tb=short \
        -x

    log_pass "Service tests completed"
}

# Run integration tests (requires running server)
run_integration_tests() {
    print_header "Integration Tests - Full Flow"

    # Check if server is running
    if curl -s "$CONTROL_PLANE_URL/health" | grep -q "healthy"; then
        log_info "Control Plane available at $CONTROL_PLANE_URL"
    else
        log_warn "Control Plane not available at $CONTROL_PLANE_URL"
        log_info "Starting Control Plane..."

        cd "$PROJECT_ROOT/control-plane"
        uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
        SERVER_PID=$!

        # Wait for server to start
        for i in {1..10}; do
            if curl -s "$CONTROL_PLANE_URL/health" | grep -q "healthy"; then
                log_pass "Control Plane started"
                break
            fi
            sleep 1
        done

        trap "kill $SERVER_PID 2>/dev/null || true" EXIT
    fi

    cd "$PROJECT_ROOT"

    PYTEST_ARGS="-v -s"

    CONTROL_PLANE_URL="$CONTROL_PLANE_URL" \
    ADMIN_TOKEN="$ADMIN_TOKEN" \
    python3 -m pytest "$TESTS_DIR/test_integrity_integration.py" $PYTEST_ARGS \
        --tb=short

    log_pass "Integration tests completed"
}

# Run with coverage
run_with_coverage() {
    print_header "Running Tests with Coverage"

    cd "$PROJECT_ROOT"

    python3 -m pytest "$TESTS_DIR/" \
        -v \
        --cov="$PROJECT_ROOT/agent/collectors" \
        --cov="$PROJECT_ROOT/control-plane/core" \
        --cov-report=term-missing \
        --cov-report=html:coverage_html \
        --tb=short

    log_info "Coverage report: $PROJECT_ROOT/coverage_html/index.html"
    log_pass "Coverage analysis completed"
}

# Watch mode - rerun on file changes
run_watch_mode() {
    print_header "Watch Mode - Rerun on Changes"

    if ! command -v inotifywait &> /dev/null; then
        log_warn "inotifywait not found, using polling"

        while true; do
            clear
            run_unit_tests || true
            run_service_tests || true
            echo ""
            log_info "Waiting for changes... (Ctrl+C to exit)"
            sleep 5
        done
    else
        while true; do
            clear
            run_unit_tests || true
            run_service_tests || true
            echo ""
            log_info "Watching for changes... (Ctrl+C to exit)"

            inotifywait -q -e modify,create,delete \
                "$PROJECT_ROOT/agent/collectors/" \
                "$PROJECT_ROOT/control-plane/core/" \
                "$TESTS_DIR/"
        done
    fi
}

# Print test summary
print_summary() {
    print_header "Test Summary"

    echo "Test Files:"
    echo "  - test_agent_integrity.py     : Agent-side hash calculation"
    echo "  - test_integrity_service.py   : Server-side verification"
    echo "  - test_integrity_integration.py: Full API flow"
    echo ""
    echo "Quick Commands:"
    echo "  pytest tests/agent/ -v -k 'test_calculate'  # Run specific tests"
    echo "  pytest tests/agent/ -v --lf                 # Rerun failed tests"
    echo "  pytest tests/agent/ -v -x                   # Stop on first failure"
}

# Main
main() {
    check_dependencies
    setup_python_path

    case "${1:-all}" in
        unit)
            run_unit_tests
            ;;
        service)
            run_service_tests
            ;;
        integration)
            run_integration_tests
            ;;
        coverage)
            run_with_coverage
            ;;
        watch)
            run_watch_mode
            ;;
        all)
            run_unit_tests
            run_service_tests
            print_summary
            ;;
        *)
            echo "Usage: $0 {unit|service|integration|coverage|watch|all}"
            exit 1
            ;;
    esac
}

main "$@"
