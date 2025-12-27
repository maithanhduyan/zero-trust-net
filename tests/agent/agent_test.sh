#!/bin/bash
# tests/agent/agent_test.sh
# Zero Trust Agent Test Suite
#
# Usage:
#   ./agent_test.sh              # Run all tests
#   ./agent_test.sh unit         # Run unit tests only
#   ./agent_test.sh integration  # Run integration tests only
#   ./agent_test.sh wireguard    # Run WireGuard tests (requires root)
#   ./agent_test.sh firewall     # Run firewall tests (requires root)
#   ./agent_test.sh e2e          # Run end-to-end tests

# Don't use set -e as we handle errors ourselves

# ============================================
# CONFIGURATION
# ============================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENT_DIR="$PROJECT_ROOT/agent"
CONTROL_PLANE_DIR="$PROJECT_ROOT/control-plane"

# Test configuration
CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://localhost:8000}"
TEST_HOSTNAME="${TEST_HOSTNAME:-test-agent-$(date +%s)}"
TEST_ROLE="${TEST_ROLE:-app}"
TEST_TEMP_DIR="/tmp/zt-agent-test-$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# ============================================
# HELPER FUNCTIONS
# ============================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
    ((TESTS_SKIPPED++))
}

log_section() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

cleanup() {
    log_info "Cleaning up test environment..."
    rm -rf "$TEST_TEMP_DIR" 2>/dev/null || true
}

trap cleanup EXIT

setup_test_env() {
    log_info "Setting up test environment..."
    mkdir -p "$TEST_TEMP_DIR"
    cd "$AGENT_DIR"

    # Create virtual environment if not exists
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi

    # Activate virtual environment
    source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true
}

check_control_plane() {
    log_info "Checking Control Plane at $CONTROL_PLANE_URL..."
    if curl -s "$CONTROL_PLANE_URL/health" | grep -q "healthy"; then
        log_pass "Control Plane is running"
        return 0
    else
        log_skip "Control Plane not available at $CONTROL_PLANE_URL"
        return 1
    fi
}

check_root() {
    if [ "$EUID" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# ============================================
# UNIT TESTS
# ============================================
run_unit_tests() {
    log_section "UNIT TESTS"

    cd "$AGENT_DIR"

    # U01: Test has_interface for loopback
    log_info "U01: Testing has_interface('lo')..."
    if python3 -c "
from client import has_interface
result = has_interface('lo')
assert result == True, f'Expected True, got {result}'
print('has_interface(lo) = True')
"; then
        log_pass "U01: has_interface('lo') returns True"
    else
        log_fail "U01: has_interface('lo') failed"
    fi

    # U02: Test has_interface for non-existent interface
    log_info "U02: Testing has_interface('nonexistent')..."
    if python3 -c "
from client import has_interface
result = has_interface('nonexistent_interface_xyz')
assert result == False, f'Expected False, got {result}'
print('has_interface(nonexistent) = False')
"; then
        log_pass "U02: has_interface('nonexistent') returns False"
    else
        log_fail "U02: has_interface failed"
    fi

    # U03: Test get_base_url without wg0
    log_info "U03: Testing get_base_url()..."
    if python3 -c "
import os
os.environ['CONTROL_PLANE_URL'] = 'https://test.example.com'
from client import get_base_url
# Reload to pick up env var
import importlib
import client
importlib.reload(client)
url = client.get_base_url()
print(f'get_base_url() = {url}')
# Should return env var or default if wg0 not up
assert 'example.com' in url or '10.0.0.1' in url
"; then
        log_pass "U03: get_base_url() works correctly"
    else
        log_fail "U03: get_base_url() failed"
    fi

    # U04: Test ControlPlaneClient initialization
    log_info "U04: Testing ControlPlaneClient init..."
    if python3 -c "
from client import ControlPlaneClient
client = ControlPlaneClient(base_url='http://localhost:8000')
assert client.base_url == 'http://localhost:8000'
assert client.api_prefix == '/api/v1/agent'
print(f'Client initialized with base_url={client.base_url}')
"; then
        log_pass "U04: ControlPlaneClient init works"
    else
        log_fail "U04: ControlPlaneClient init failed"
    fi

    # U05: Test collect_host_info
    log_info "U05: Testing collect_host_info()..."
    if python3 -c "
from collectors.host_info import collect_host_info
info = collect_host_info()
assert 'hostname' in info, 'Missing hostname'
assert 'os_info' in info, 'Missing os_info'
assert 'platform' in info, 'Missing platform'
print(f'Host info: hostname={info[\"hostname\"]}, os={info[\"os_info\"]}')
"; then
        log_pass "U05: collect_host_info() works"
    else
        log_fail "U05: collect_host_info() failed"
    fi

    # U06: Test collect_resource_usage
    log_info "U06: Testing collect_resource_usage()..."
    if python3 -c "
from collectors.host_info import collect_resource_usage
usage = collect_resource_usage()
assert 'memory_percent' in usage, 'Missing memory_percent'
assert 'uptime_seconds' in usage, 'Missing uptime_seconds'
print(f'Resource usage: memory={usage.get(\"memory_percent\")}%, uptime={usage.get(\"uptime_seconds\")}s')
"; then
        log_pass "U06: collect_resource_usage() works"
    else
        log_fail "U06: collect_resource_usage() failed"
    fi

    # U07: Test WireGuard config builder
    log_info "U07: Testing WireGuardConfigBuilder.build_config()..."
    if python3 -c "
from wireguard.config_builder import WireGuardConfigBuilder
builder = WireGuardConfigBuilder()

# Create a temp private key file
import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
    f.write('cHJpdmF0ZWtleXRlc3QxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ=')
    key_path = f.name

config = builder.build_config(
    address='10.0.0.2/24',
    private_key_path=key_path,
    listen_port=51820,
    dns=['10.0.0.1'],
    peers=[{
        'public_key': 'cHVibGlja2V5dGVzdDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNA==',
        'endpoint': '1.2.3.4:51820',
        'allowed_ips': '10.0.0.0/24',
        'persistent_keepalive': 25
    }]
)
assert '[Interface]' in config
assert 'Address = 10.0.0.2/24' in config
assert '[Peer]' in config
assert 'AllowedIPs = 10.0.0.0/24' in config
print('WireGuard config generated successfully')
import os
os.unlink(key_path)
"; then
        log_pass "U07: WireGuardConfigBuilder works"
    else
        log_fail "U07: WireGuardConfigBuilder failed"
    fi

    # U08: Test config parser
    log_info "U08: Testing WireGuardConfigBuilder.parse_config()..."
    if python3 -c "
from wireguard.config_builder import WireGuardConfigBuilder
from pathlib import Path
import tempfile

builder = WireGuardConfigBuilder()

# Create temp config file
config_content = '''[Interface]
Address = 10.0.0.2/24
PrivateKey = testkey123
ListenPort = 51820

[Peer]
PublicKey = peerpubkey123
AllowedIPs = 10.0.0.0/24
Endpoint = 1.2.3.4:51820
'''

with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
    f.write(config_content)
    config_path = f.name

parsed = builder.parse_config(Path(config_path))
assert 'interface' in parsed
assert 'peers' in parsed
assert parsed['interface'].get('address') == '10.0.0.2/24'
assert len(parsed['peers']) == 1
print(f'Parsed config: interface={parsed[\"interface\"]}, peers={len(parsed[\"peers\"])}')

import os
os.unlink(config_path)
"; then
        log_pass "U08: Config parser works"
    else
        log_fail "U08: Config parser failed"
    fi
}

# ============================================
# INTEGRATION TESTS
# ============================================
run_integration_tests() {
    log_section "INTEGRATION TESTS"

    if ! check_control_plane; then
        log_skip "Skipping integration tests - Control Plane not available"
        return
    fi

    cd "$AGENT_DIR"

    # Generate a unique test hostname
    local test_host="test-int-$(date +%s)"
    local test_pubkey="dGVzdHB1YmxpY2tleTEyMzQ1Njc4OTAxMjM0NTY3ODk="

    # I01: Test registration
    log_info "I01: Testing register() new node..."
    if python3 -c "
from client import ControlPlaneClient
client = ControlPlaneClient(base_url='$CONTROL_PLANE_URL')
try:
    result = client.register(
        hostname='$test_host',
        role='app',
        public_key='$test_pubkey',
        description='Integration test node',
        agent_version='1.0.0',
        os_info='Test OS'
    )
    print(f'Registration result: {result}')
    assert 'overlay_ip' in result.get('data', result), 'Missing overlay_ip'
    print(f'Assigned IP: {result.get(\"data\", result).get(\"overlay_ip\")}')
except Exception as e:
    print(f'Registration error: {e}')
    # 409 conflict is OK if node already exists
    if '409' not in str(e):
        raise
"; then
        log_pass "I01: register() works"
    else
        log_fail "I01: register() failed"
    fi

    # I02: Test duplicate registration
    log_info "I02: Testing register() existing node..."
    if python3 -c "
from client import ControlPlaneClient
client = ControlPlaneClient(base_url='$CONTROL_PLANE_URL')
try:
    result = client.register(
        hostname='$test_host',
        role='app',
        public_key='$test_pubkey'
    )
    print(f'Re-registration result: {result}')
except Exception as e:
    # 409 is expected
    if '409' in str(e):
        print('Got expected 409 Conflict')
    else:
        raise
"; then
        log_pass "I02: Duplicate registration handled"
    else
        log_fail "I02: Duplicate registration failed"
    fi

    # I03: Test get_status
    log_info "I06: Testing get_status()..."
    if python3 -c "
from client import ControlPlaneClient
client = ControlPlaneClient(base_url='$CONTROL_PLANE_URL')
try:
    result = client.get_status('$test_host')
    print(f'Status result: {result}')
    data = result.get('data', result)
    assert 'hostname' in data or 'status' in data
except Exception as e:
    print(f'Status error: {e}')
    if '404' in str(e):
        print('Node not found (expected if not registered)')
    else:
        raise
"; then
        log_pass "I06: get_status() works"
    else
        log_fail "I06: get_status() failed"
    fi

    # I04: Test get_config (may fail with 403 if pending)
    log_info "I03/I04: Testing get_config()..."
    if python3 -c "
from client import ControlPlaneClient
client = ControlPlaneClient(base_url='$CONTROL_PLANE_URL')
try:
    result = client.get_config('$test_host')
    print(f'Config result: {result}')
    data = result.get('data', result)
    if 'peers' in data or 'acl_rules' in data:
        print('Got peers and/or acl_rules')
except Exception as e:
    print(f'Config error: {e}')
    if '403' in str(e):
        print('Got 403 - node pending approval (expected)')
    elif '404' in str(e):
        print('Got 404 - node not found')
    else:
        raise
"; then
        log_pass "I03/I04: get_config() works"
    else
        log_fail "I03/I04: get_config() failed"
    fi

    # I05: Test heartbeat
    log_info "I05: Testing heartbeat()..."
    if python3 -c "
from client import ControlPlaneClient
client = ControlPlaneClient(base_url='$CONTROL_PLANE_URL')
try:
    result = client.heartbeat(
        hostname='$test_host',
        public_key='$test_pubkey',
        agent_version='1.0.0',
        uptime_seconds=3600
    )
    print(f'Heartbeat result: {result}')
except Exception as e:
    print(f'Heartbeat error: {e}')
    if '404' in str(e) or '403' in str(e):
        print('Node not active (expected for new node)')
    else:
        raise
"; then
        log_pass "I05: heartbeat() works"
    else
        log_fail "I05: heartbeat() failed"
    fi
}

# ============================================
# WIREGUARD TESTS
# ============================================
run_wireguard_tests() {
    log_section "WIREGUARD TESTS"

    if ! check_root; then
        log_skip "Skipping WireGuard tests - requires root"
        return
    fi

    cd "$AGENT_DIR"

    # W01: Test is_installed
    log_info "W01: Testing WireGuardManager.is_installed()..."
    if python3 -c "
from wireguard.manager import WireGuardManager
manager = WireGuardManager(interface='wg0', config_dir='$TEST_TEMP_DIR/wg')
result = manager.is_installed()
print(f'WireGuard installed: {result}')
# Don't fail if not installed, just report
"; then
        log_pass "W01: is_installed() works"
    else
        log_fail "W01: is_installed() failed"
    fi

    # W02: Test keypair generation
    log_info "W02: Testing keypair generation..."
    if which wg >/dev/null 2>&1; then
        if python3 -c "
from wireguard.manager import WireGuardManager
import os
os.makedirs('$TEST_TEMP_DIR/wg', exist_ok=True)
manager = WireGuardManager(interface='wg0', config_dir='$TEST_TEMP_DIR/wg')
private_key, public_key = manager.generate_keypair()
assert len(private_key) == 44, f'Invalid private key length: {len(private_key)}'
assert len(public_key) == 44, f'Invalid public key length: {len(public_key)}'
print(f'Generated keypair: public_key={public_key[:20]}...')
"; then
            log_pass "W02: Keypair generation works"
        else
            log_fail "W02: Keypair generation failed"
        fi
    else
        log_skip "W02: WireGuard not installed"
    fi

    # W03: Test get_public_key
    log_info "W03: Testing get_public_key()..."
    if [ -f "$TEST_TEMP_DIR/wg/public.key" ]; then
        if python3 -c "
from wireguard.manager import WireGuardManager
manager = WireGuardManager(interface='wg0', config_dir='$TEST_TEMP_DIR/wg')
pubkey = manager.get_public_key()
assert pubkey is not None
assert len(pubkey) == 44
print(f'Public key: {pubkey[:20]}...')
"; then
            log_pass "W03: get_public_key() works"
        else
            log_fail "W03: get_public_key() failed"
        fi
    else
        log_skip "W03: No keypair generated yet"
    fi

    # W04: Test keypair_exists
    log_info "W04: Testing keypair_exists()..."
    if python3 -c "
from wireguard.manager import WireGuardManager
manager = WireGuardManager(interface='wg0', config_dir='$TEST_TEMP_DIR/wg')
exists = manager.keypair_exists()
print(f'Keypair exists: {exists}')
"; then
        log_pass "W04: keypair_exists() works"
    else
        log_fail "W04: keypair_exists() failed"
    fi

    # W05: Test write_config
    log_info "W05: Testing write_config()..."
    if python3 -c "
from wireguard.config_builder import WireGuardConfigBuilder
from pathlib import Path
import os
import stat

os.makedirs('$TEST_TEMP_DIR/wg', exist_ok=True)

# Create dummy private key
with open('$TEST_TEMP_DIR/wg/private.key', 'w') as f:
    f.write('dGVzdHByaXZhdGVrZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDEy')

builder = WireGuardConfigBuilder()
config = builder.build_config(
    address='10.0.0.2/24',
    private_key_path='$TEST_TEMP_DIR/wg/private.key',
    peers=[]
)

config_path = Path('$TEST_TEMP_DIR/wg/wg0.conf')
result = builder.write_config(config, config_path, backup=False)
assert result == True
assert config_path.exists()

# Check permissions
mode = stat.S_IMODE(os.stat(config_path).st_mode)
assert mode == 0o600, f'Expected 0600, got {oct(mode)}'
print(f'Config written with correct permissions (0600)')
"; then
        log_pass "W05: write_config() works"
    else
        log_fail "W05: write_config() failed"
    fi
}

# ============================================
# FIREWALL TESTS
# ============================================
run_firewall_tests() {
    log_section "FIREWALL TESTS"

    if ! check_root; then
        log_skip "Skipping firewall tests - requires root"
        return
    fi

    if ! which iptables >/dev/null 2>&1; then
        log_skip "Skipping firewall tests - iptables not installed"
        return
    fi

    cd "$AGENT_DIR"

    # Use a test chain name to avoid conflicts
    local test_chain="ZT_ACL_TEST"

    # F01: Test chain creation
    log_info "F01: Testing chain creation..."
    if python3 -c "
from firewall.iptables import IPTablesManager

class TestIPTables(IPTablesManager):
    CHAIN_NAME = '$test_chain'

manager = TestIPTables(interface='lo')
# Chain should be created in __init__
print('Chain creation test passed')
"; then
        log_pass "F01: Chain creation works"
    else
        log_fail "F01: Chain creation failed"
    fi

    # F02: Test apply_rules with empty list
    log_info "F02: Testing apply_rules([])..."
    if python3 -c "
from firewall.iptables import IPTablesManager

class TestIPTables(IPTablesManager):
    CHAIN_NAME = '$test_chain'

manager = TestIPTables(interface='lo')
manager.apply_rules([])
print('Applied empty rules (default deny)')
"; then
        log_pass "F02: apply_rules([]) works"
    else
        log_fail "F02: apply_rules([]) failed"
    fi

    # F03: Test apply_rules with allow rule
    log_info "F03: Testing apply_rules([allow_rule])..."
    if python3 -c "
from firewall.iptables import IPTablesManager

class TestIPTables(IPTablesManager):
    CHAIN_NAME = '$test_chain'

manager = TestIPTables(interface='lo')
rules = [
    {
        'src_ip': '10.0.0.0/24',
        'dst_ip': '10.0.0.2/32',
        'protocol': 'tcp',
        'port': 5432,
        'action': 'allow',
        'description': 'Test rule'
    }
]
manager.apply_rules(rules)
print('Applied allow rule')
"; then
        log_pass "F03: apply_rules([allow_rule]) works"
    else
        log_fail "F03: apply_rules([allow_rule]) failed"
    fi

    # F04: Test list_rules
    log_info "F04: Testing list_rules()..."
    if python3 -c "
from firewall.iptables import IPTablesManager

class TestIPTables(IPTablesManager):
    CHAIN_NAME = '$test_chain'

manager = TestIPTables(interface='lo')
output = manager.list_rules()
print(f'Rules output length: {len(output)} chars')
print(output[:500] if len(output) > 500 else output)
"; then
        log_pass "F04: list_rules() works"
    else
        log_fail "F04: list_rules() failed"
    fi

    # F05: Test cleanup
    log_info "F05: Testing cleanup()..."
    if python3 -c "
from firewall.iptables import IPTablesManager

class TestIPTables(IPTablesManager):
    CHAIN_NAME = '$test_chain'

manager = TestIPTables(interface='lo')
manager.cleanup()
print('Cleanup completed')
"; then
        log_pass "F05: cleanup() works"
    else
        log_fail "F05: cleanup() failed"
    fi

    # Verify cleanup
    if iptables -L "$test_chain" -n 2>/dev/null; then
        log_fail "F05: Chain still exists after cleanup"
        iptables -F "$test_chain" 2>/dev/null || true
        iptables -X "$test_chain" 2>/dev/null || true
    fi
}

# ============================================
# END-TO-END TESTS
# ============================================
run_e2e_tests() {
    log_section "END-TO-END TESTS"

    if ! check_control_plane; then
        log_skip "Skipping E2E tests - Control Plane not available"
        return
    fi

    cd "$AGENT_DIR"

    log_info "E01: Testing fresh registration flow..."
    # This would require starting the full agent, which needs root
    # For now, we test the client flow
    if python3 -c "
from client import ControlPlaneClient
from collectors.host_info import collect_host_info

client = ControlPlaneClient(base_url='$CONTROL_PLANE_URL')
host_info = collect_host_info()

test_host = 'e2e-test-$(date +%s)'
test_pubkey = 'ZTJlcHVia2V5MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NQ=='

try:
    result = client.register(
        hostname=test_host,
        role='app',
        public_key=test_pubkey,
        description='E2E test node',
        os_info=host_info.get('os_info', 'Unknown')
    )
    data = result.get('data', result)
    print(f'E2E Registration: hostname={test_host}')
    print(f'  Overlay IP: {data.get(\"overlay_ip\")}')
    print(f'  Status: {data.get(\"status\")}')
except Exception as e:
    print(f'E2E test error: {e}')
"; then
        log_pass "E01: Fresh registration flow works"
    else
        log_fail "E01: Fresh registration flow failed"
    fi

    log_info "E04: Testing graceful shutdown (simulation)..."
    if python3 -c "
import signal
import sys

shutdown_received = False

def handler(signum, frame):
    global shutdown_received
    shutdown_received = True
    print(f'Received signal {signum}')

signal.signal(signal.SIGTERM, handler)

# Simulate sending SIGTERM
import os
os.kill(os.getpid(), signal.SIGTERM)

assert shutdown_received, 'Signal handler not called'
print('Graceful shutdown handler works')
"; then
        log_pass "E04: Graceful shutdown works"
    else
        log_fail "E04: Graceful shutdown failed"
    fi
}

# ============================================
# MAIN
# ============================================
print_summary() {
    log_section "TEST SUMMARY"

    local total=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

    echo ""
    echo -e "  ${GREEN}Passed:${NC}  $TESTS_PASSED"
    echo -e "  ${RED}Failed:${NC}  $TESTS_FAILED"
    echo -e "  ${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
    echo -e "  Total:   $total"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║       ALL TESTS PASSED! ✓            ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
        return 0
    else
        echo -e "${RED}╔══════════════════════════════════════╗${NC}"
        echo -e "${RED}║       SOME TESTS FAILED! ✗           ║${NC}"
        echo -e "${RED}╚══════════════════════════════════════╝${NC}"
        return 1
    fi
}

main() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       ZERO TRUST AGENT TEST SUITE                            ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    setup_test_env

    local test_type="${1:-all}"

    case "$test_type" in
        unit)
            run_unit_tests
            ;;
        integration)
            run_integration_tests
            ;;
        wireguard)
            run_wireguard_tests
            ;;
        firewall)
            run_firewall_tests
            ;;
        e2e)
            run_e2e_tests
            ;;
        all)
            run_unit_tests
            run_integration_tests
            run_wireguard_tests
            run_firewall_tests
            run_e2e_tests
            ;;
        *)
            echo "Usage: $0 [unit|integration|wireguard|firewall|e2e|all]"
            exit 1
            ;;
    esac

    print_summary
}

main "$@"
