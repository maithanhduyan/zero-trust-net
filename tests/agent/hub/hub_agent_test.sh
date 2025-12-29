#!/bin/bash
# =============================================================================
# Zero Trust Hub Agent Test Suite
# =============================================================================
# Tests for Hub Agent components:
# - WireGuard Manager (server mode)
# - Peer Manager
# - Firewall (iptables, forwarding)
# - Status collectors
# - Command Executor
# - WebSocket Handler (mock)
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
HUB_AGENT_DIR="$PROJECT_ROOT/agent/hub"
TEST_CONFIG_DIR="/tmp/hub-agent-test"
TEST_INTERFACE="wg-test"
TEST_LOG_FILE="/tmp/hub-agent-test.log"

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# =============================================================================
# Utility Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
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
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}======================================${NC}"
}

cleanup() {
    log_info "Cleaning up test environment..."

    # Remove test WireGuard interface if exists
    if ip link show "$TEST_INTERFACE" &>/dev/null; then
        ip link delete "$TEST_INTERFACE" 2>/dev/null || true
    fi

    # Remove test config directory
    rm -rf "$TEST_CONFIG_DIR"

    # Remove test iptables chains
    iptables -D FORWARD -j ZT_HUB_FORWARD 2>/dev/null || true
    iptables -F ZT_HUB_FORWARD 2>/dev/null || true
    iptables -X ZT_HUB_FORWARD 2>/dev/null || true
    iptables -t nat -D POSTROUTING -j ZT_HUB_NAT 2>/dev/null || true
    iptables -t nat -F ZT_HUB_NAT 2>/dev/null || true
    iptables -t nat -X ZT_HUB_NAT 2>/dev/null || true

    log_info "Cleanup complete"
}

setup_test_env() {
    log_info "Setting up test environment..."

    # Create test config directory
    mkdir -p "$TEST_CONFIG_DIR"
    chmod 700 "$TEST_CONFIG_DIR"

    # Generate test WireGuard keys
    wg genkey > "$TEST_CONFIG_DIR/private.key"
    cat "$TEST_CONFIG_DIR/private.key" | wg pubkey > "$TEST_CONFIG_DIR/public.key"

    # Create minimal WireGuard config
    cat > "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" << EOF
[Interface]
PrivateKey = $(cat "$TEST_CONFIG_DIR/private.key")
Address = 10.99.99.1/24
ListenPort = 51899
EOF
    chmod 600 "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf"

    log_info "Test environment ready"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Error: This script must be run as root${NC}"
        exit 1
    fi
}

check_dependencies() {
    log_section "Checking Dependencies"

    local deps=("python3" "wg" "wg-quick" "iptables" "ip")
    local missing=()

    for dep in "${deps[@]}"; do
        if command -v "$dep" &>/dev/null; then
            log_success "Found: $dep"
        else
            log_fail "Missing: $dep"
            missing+=("$dep")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}Missing dependencies: ${missing[*]}${NC}"
        exit 1
    fi
}

# =============================================================================
# Test: Python Syntax Check
# =============================================================================

test_python_syntax() {
    log_section "Python Syntax Check"

    local files=(
        "hub_agent.py"
        "websocket_handler.py"
        "command_executor.py"
        "wireguard/manager.py"
        "wireguard/peer_manager.py"
        "firewall/iptables.py"
        "firewall/forwarding.py"
        "status/interface_status.py"
        "status/peer_stats.py"
    )

    for file in "${files[@]}"; do
        if python3 -m py_compile "$HUB_AGENT_DIR/$file" 2>/dev/null; then
            log_success "Syntax OK: $file"
        else
            log_fail "Syntax error: $file"
        fi
    done
}

# =============================================================================
# Test: Python Imports
# =============================================================================

test_python_imports() {
    log_section "Python Import Check"

    cd "$HUB_AGENT_DIR"

    # Test individual module imports
    local modules=(
        "from wireguard.manager import WireGuardManager"
        "from wireguard.peer_manager import PeerManager"
        "from firewall.iptables import HubFirewall"
        "from firewall.forwarding import ForwardingManager"
        "from status.interface_status import InterfaceStatus"
        "from status.peer_stats import PeerStats"
        "from command_executor import CommandExecutor"
    )

    for mod in "${modules[@]}"; do
        if python3 -c "$mod" 2>/dev/null; then
            log_success "Import OK: $mod"
        else
            log_fail "Import failed: $mod"
        fi
    done

    cd - > /dev/null
}

# =============================================================================
# Test: WireGuard Manager
# =============================================================================

test_wireguard_manager() {
    log_section "WireGuard Manager Tests"

    cd "$HUB_AGENT_DIR"

    # Test 1: Check WireGuard installed
    log_info "Test: check_wireguard_installed()"
    python3 << 'EOF'
from wireguard.manager import WireGuardManager
wg = WireGuardManager("wg-test", "/tmp/hub-agent-test")
result = wg.check_wireguard_installed()
print(f"RESULT:{result}")
EOF
    local result=$?
    if [[ $result -eq 0 ]]; then
        log_success "check_wireguard_installed() works"
    else
        log_fail "check_wireguard_installed() failed"
    fi

    # Test 2: Interface up/down (async)
    log_info "Test: bring_up_interface() / bring_down_interface()"
    python3 << EOF
import asyncio
from wireguard.manager import WireGuardManager

async def test():
    wg = WireGuardManager("$TEST_INTERFACE", "$TEST_CONFIG_DIR")

    # Bring up
    up_result = await wg.bring_up_interface()
    print(f"UP_RESULT:{up_result}")

    # Check if up
    is_up = await wg.is_interface_up()
    print(f"IS_UP:{is_up}")

    # Bring down
    down_result = await wg.bring_down_interface()
    print(f"DOWN_RESULT:{down_result}")

    return up_result and is_up

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "Interface up/down works"
    else
        log_fail "Interface up/down failed"
    fi

    # Test 3: Add/Remove peer
    log_info "Test: add_peer() / remove_peer()"

    # First bring up the interface
    wg-quick up "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    # Generate a test peer key
    local peer_key=$(wg genkey | wg pubkey)

    python3 << EOF
import asyncio
from wireguard.manager import WireGuardManager

async def test():
    wg = WireGuardManager("$TEST_INTERFACE", "$TEST_CONFIG_DIR")

    # Add peer
    add_result = await wg.add_peer(
        public_key="$peer_key",
        allowed_ips="10.99.99.2/32"
    )
    print(f"ADD_RESULT:{add_result}")

    # Check peer exists
    peers = await wg.get_peers()
    peer_exists = any(p['public_key'] == "$peer_key" for p in peers)
    print(f"PEER_EXISTS:{peer_exists}")

    # Remove peer
    remove_result = await wg.remove_peer("$peer_key")
    print(f"REMOVE_RESULT:{remove_result}")

    # Check peer removed
    peers_after = await wg.get_peers()
    peer_removed = not any(p['public_key'] == "$peer_key" for p in peers_after)
    print(f"PEER_REMOVED:{peer_removed}")

    return add_result and peer_exists and remove_result and peer_removed

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "add_peer/remove_peer works"
    else
        log_fail "add_peer/remove_peer failed"
    fi

    # Cleanup
    wg-quick down "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    cd - > /dev/null
}

# =============================================================================
# Test: Peer Manager
# =============================================================================

test_peer_manager() {
    log_section "Peer Manager Tests"

    cd "$HUB_AGENT_DIR"

    # Bring up test interface
    wg-quick up "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    # Generate test peer keys
    local peer1_key=$(wg genkey | wg pubkey)
    local peer2_key=$(wg genkey | wg pubkey)
    local peer3_key=$(wg genkey | wg pubkey)

    # Test: sync_peers
    log_info "Test: sync_peers()"
    python3 << EOF
import asyncio
from wireguard.manager import WireGuardManager
from wireguard.peer_manager import PeerManager

async def test():
    wg = WireGuardManager("$TEST_INTERFACE", "$TEST_CONFIG_DIR")
    pm = PeerManager(wg)

    # Sync with desired peers
    desired_peers = [
        {"public_key": "$peer1_key", "allowed_ips": "10.99.99.10/32"},
        {"public_key": "$peer2_key", "allowed_ips": "10.99.99.11/32"},
    ]

    result = await pm.sync_peers(desired_peers)
    print(f"SYNC_RESULT: added={result['added']}, removed={result['removed']}")

    # Verify peer count
    count = await pm.get_peer_count()
    print(f"PEER_COUNT:{count}")

    # Sync again with different list (should remove peer2, add peer3)
    desired_peers_v2 = [
        {"public_key": "$peer1_key", "allowed_ips": "10.99.99.10/32"},
        {"public_key": "$peer3_key", "allowed_ips": "10.99.99.12/32"},
    ]

    result2 = await pm.sync_peers(desired_peers_v2)
    print(f"SYNC2_RESULT: added={result2['added']}, removed={result2['removed']}")

    # Verify final count
    final_count = await pm.get_peer_count()
    print(f"FINAL_COUNT:{final_count}")

    # Cleanup - remove all
    await pm.sync_peers([])

    return result['added'] == 2 and result2['removed'] == 1 and result2['added'] == 1

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "sync_peers() works correctly"
    else
        log_fail "sync_peers() failed"
    fi

    # Cleanup
    wg-quick down "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    cd - > /dev/null
}

# =============================================================================
# Test: Firewall (iptables)
# =============================================================================

test_firewall_iptables() {
    log_section "Firewall (iptables) Tests"

    cd "$HUB_AGENT_DIR"

    # Test: Initialize chains
    log_info "Test: initialize() and setup_masquerade()"
    python3 << 'EOF'
import asyncio
from firewall.iptables import HubFirewall

async def test():
    fw = HubFirewall("wg-test")

    # Initialize (creates chains)
    await fw.initialize()
    print("INIT:OK")

    # Setup masquerade
    await fw.setup_masquerade()
    print("MASQ:OK")

    # Setup forwarding rules
    await fw.setup_forwarding_rules()
    print("FWD:OK")

    # Get rules
    rules = await fw.get_rules()
    print(f"RULES_COUNT:{len(rules)}")

    return True

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "Firewall initialization works"
    else
        log_fail "Firewall initialization failed"
    fi

    # Verify chains exist
    log_info "Verifying iptables chains..."
    if iptables -L ZT_HUB_FORWARD -n &>/dev/null; then
        log_success "ZT_HUB_FORWARD chain exists"
    else
        log_fail "ZT_HUB_FORWARD chain missing"
    fi

    if iptables -t nat -L ZT_HUB_NAT -n &>/dev/null; then
        log_success "ZT_HUB_NAT chain exists"
    else
        log_fail "ZT_HUB_NAT chain missing"
    fi

    # Test: Add ACL rule
    log_info "Test: add_acl_rule()"
    python3 << 'EOF'
import asyncio
from firewall.iptables import HubFirewall

async def test():
    fw = HubFirewall("wg-test")
    await fw.initialize()

    # Add allow rule
    await fw.add_acl_rule(
        action="ACCEPT",
        source="10.99.99.0/24",
        destination="10.99.99.0/24",
        protocol="tcp",
        port=5432,
        comment="test-postgres"
    )
    print("ACL_ADDED:OK")

    # Get rules and verify
    rules = await fw.get_rules()
    has_rule = any("5432" in r for r in rules)
    print(f"RULE_EXISTS:{has_rule}")

    return has_rule

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "add_acl_rule() works"
    else
        log_fail "add_acl_rule() failed"
    fi

    # Test: Clear ACL rules
    log_info "Test: clear_acl_rules()"
    python3 << 'EOF'
import asyncio
from firewall.iptables import HubFirewall

async def test():
    fw = HubFirewall("wg-test")
    await fw.clear_acl_rules()
    print("CLEAR:OK")
    return True

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "clear_acl_rules() works"
    else
        log_fail "clear_acl_rules() failed"
    fi

    cd - > /dev/null
}

# =============================================================================
# Test: IP Forwarding
# =============================================================================

test_ip_forwarding() {
    log_section "IP Forwarding Tests"

    cd "$HUB_AGENT_DIR"

    # Save current state
    local original_forward=$(cat /proc/sys/net/ipv4/ip_forward)

    # Test: Enable forwarding
    log_info "Test: enable_ip_forward()"
    python3 << 'EOF'
from firewall.forwarding import ForwardingManager

fm = ForwardingManager()
fm.enable_ip_forward(persist=False)
print("ENABLE:OK")

# Verify
is_enabled = fm.is_forwarding_enabled()
print(f"IS_ENABLED:{is_enabled}")
EOF

    if [[ $(cat /proc/sys/net/ipv4/ip_forward) == "1" ]]; then
        log_success "IP forwarding enabled"
    else
        log_fail "IP forwarding not enabled"
    fi

    # Test: Check state
    log_info "Test: is_forwarding_enabled()"
    python3 << 'EOF'
from firewall.forwarding import ForwardingManager

fm = ForwardingManager()
result = fm.is_forwarding_enabled()
print(f"FORWARD_ENABLED:{result}")
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "is_forwarding_enabled() returns True"
    else
        log_fail "is_forwarding_enabled() returns False"
    fi

    # Restore original state
    echo "$original_forward" > /proc/sys/net/ipv4/ip_forward

    cd - > /dev/null
}

# =============================================================================
# Test: Status Collectors
# =============================================================================

test_status_collectors() {
    log_section "Status Collectors Tests"

    cd "$HUB_AGENT_DIR"

    # Bring up test interface for status tests
    wg-quick up "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    # Test: InterfaceStatus
    log_info "Test: InterfaceStatus.get_full_status()"
    python3 << EOF
import asyncio
from status.interface_status import InterfaceStatus

async def test():
    status = InterfaceStatus("$TEST_INTERFACE")

    result = await status.get_full_status()
    print(f"INTERFACE:{result.get('interface')}")
    print(f"IS_UP:{result.get('is_up')}")
    print(f"PEER_COUNT:{result.get('peer_count', 0)}")

    # Check health
    is_healthy = await status.is_healthy()
    print(f"IS_HEALTHY:{is_healthy}")

    return result.get('is_up', False)

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "InterfaceStatus works"
    else
        log_fail "InterfaceStatus failed"
    fi

    # Test: PeerStats
    log_info "Test: PeerStats.get_all_stats()"
    python3 << EOF
import asyncio
from status.peer_stats import PeerStats

async def test():
    stats = PeerStats("$TEST_INTERFACE")

    result = await stats.get_all_stats()
    print(f"INTERFACE:{result.get('interface')}")
    print(f"TOTAL_PEERS:{result['summary']['total_peers']}")

    return 'summary' in result

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "PeerStats works"
    else
        log_fail "PeerStats failed"
    fi

    # Cleanup
    wg-quick down "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    cd - > /dev/null
}

# =============================================================================
# Test: Command Executor
# =============================================================================

test_command_executor() {
    log_section "Command Executor Tests"

    cd "$HUB_AGENT_DIR"

    # Bring up test interface
    wg-quick up "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    # Generate test peer key
    local test_peer_key=$(wg genkey | wg pubkey)

    log_info "Test: CommandExecutor.execute()"
    python3 << EOF
import asyncio
from wireguard.manager import WireGuardManager
from wireguard.peer_manager import PeerManager
from firewall.iptables import HubFirewall
from status.interface_status import InterfaceStatus
from status.peer_stats import PeerStats
from command_executor import CommandExecutor

async def test():
    # Initialize components
    wg = WireGuardManager("$TEST_INTERFACE", "$TEST_CONFIG_DIR")
    pm = PeerManager(wg)
    fw = HubFirewall("$TEST_INTERFACE")
    status = InterfaceStatus("$TEST_INTERFACE")
    stats = PeerStats("$TEST_INTERFACE")

    executor = CommandExecutor(wg, pm, fw, status, stats)

    # Test: ping command
    result = await executor.execute("ping", {})
    print(f"PING_SUCCESS:{result['success']}")
    print(f"PING_DATA:{result.get('data', {}).get('pong')}")

    # Test: add_peer command
    result = await executor.execute("add_peer", {
        "public_key": "$test_peer_key",
        "allowed_ips": "10.99.99.50/32"
    })
    print(f"ADD_PEER_SUCCESS:{result['success']}")

    # Test: get_status command
    result = await executor.execute("get_status", {})
    print(f"GET_STATUS_SUCCESS:{result['success']}")
    print(f"INTERFACE_UP:{result.get('data', {}).get('is_up')}")

    # Test: remove_peer command
    result = await executor.execute("remove_peer", {
        "public_key": "$test_peer_key"
    })
    print(f"REMOVE_PEER_SUCCESS:{result['success']}")

    # Test: unknown command
    result = await executor.execute("unknown_command", {})
    print(f"UNKNOWN_HANDLED:{not result['success']}")

    return True

result = asyncio.run(test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "CommandExecutor works"
    else
        log_fail "CommandExecutor failed"
    fi

    # Cleanup
    wg-quick down "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    cd - > /dev/null
}

# =============================================================================
# Test: WebSocket Handler (Mock)
# =============================================================================

test_websocket_handler() {
    log_section "WebSocket Handler Tests (Mock)"

    cd "$HUB_AGENT_DIR"

    # Test: WebSocketHandler initialization
    log_info "Test: WebSocketHandler initialization"
    python3 << 'EOF'
from websocket_handler import WebSocketHandler

# Mock command executor
class MockExecutor:
    async def execute(self, cmd_type, payload):
        return {"success": True, "data": {"mock": True}}

    async def get_interface_status(self):
        return {"is_up": True, "peer_count": 0}

handler = WebSocketHandler(
    url="ws://localhost:8000/api/v1/ws/hub",
    api_key="test-key",
    command_executor=MockExecutor()
)

print(f"URL:{handler.url}")
print(f"IS_CONNECTED:{handler.is_connected()}")
print("INIT:OK")
EOF
    if [[ $? -eq 0 ]]; then
        log_success "WebSocketHandler initialization works"
    else
        log_fail "WebSocketHandler initialization failed"
    fi

    # Note: Full WebSocket tests require a running Control Plane
    log_skip "WebSocket connection test (requires running Control Plane)"

    cd - > /dev/null
}

# =============================================================================
# Test: Hub Agent Integration
# =============================================================================

test_hub_agent_integration() {
    log_section "Hub Agent Integration Tests"

    cd "$HUB_AGENT_DIR"

    # Test: HubAgent initialization (without starting)
    log_info "Test: HubAgent initialization"
    python3 << EOF
import os
os.environ['HUB_API_KEY'] = 'test-api-key'

# Prevent log file creation in test
import logging
logging.disable(logging.CRITICAL)

from hub_agent import HubAgent

agent = HubAgent(
    control_plane_url="ws://localhost:8000/api/v1/ws/hub",
    api_key="test-key",
    interface="$TEST_INTERFACE",
    config_dir="$TEST_CONFIG_DIR",
    status_interval=30
)

print(f"INTERFACE:{agent.interface}")
print(f"CONFIG_DIR:{agent.config_dir}")
print(f"STATUS_INTERVAL:{agent.status_interval}")
print("INIT:OK")
EOF
    if [[ $? -eq 0 ]]; then
        log_success "HubAgent initialization works"
    else
        log_fail "HubAgent initialization failed"
    fi

    # Test: Prerequisites validation
    log_info "Test: _validate_prerequisites()"
    python3 << EOF
import os
os.environ['HUB_API_KEY'] = 'test-api-key'

import logging
logging.disable(logging.CRITICAL)

from hub_agent import HubAgent

agent = HubAgent(
    control_plane_url="ws://localhost:8000/api/v1/ws/hub",
    api_key="test-key",
    interface="$TEST_INTERFACE",
    config_dir="$TEST_CONFIG_DIR"
)

result = agent._validate_prerequisites()
print(f"PREREQ_RESULT:{result}")
EOF
    if [[ $? -eq 0 ]]; then
        log_success "_validate_prerequisites() works"
    else
        log_fail "_validate_prerequisites() failed"
    fi

    cd - > /dev/null
}

# =============================================================================
# Test: End-to-End Scenario
# =============================================================================

test_e2e_scenario() {
    log_section "End-to-End Scenario Test"

    cd "$HUB_AGENT_DIR"

    # Bring up test interface
    wg-quick up "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    log_info "Simulating full peer lifecycle..."

    # Generate peer keys
    local client1_key=$(wg genkey | wg pubkey)
    local client2_key=$(wg genkey | wg pubkey)

    python3 << EOF
import asyncio
from wireguard.manager import WireGuardManager
from wireguard.peer_manager import PeerManager
from firewall.iptables import HubFirewall
from firewall.forwarding import ForwardingManager
from status.interface_status import InterfaceStatus
from status.peer_stats import PeerStats

async def e2e_test():
    print("=== E2E Test Start ===")

    # Initialize components
    wg = WireGuardManager("$TEST_INTERFACE", "$TEST_CONFIG_DIR")
    pm = PeerManager(wg)
    fw = HubFirewall("$TEST_INTERFACE")
    fwd = ForwardingManager()
    status = InterfaceStatus("$TEST_INTERFACE")
    stats = PeerStats("$TEST_INTERFACE")

    # Step 1: Enable forwarding
    print("Step 1: Enable IP forwarding")
    fwd.enable_ip_forward(persist=False)

    # Step 2: Setup firewall
    print("Step 2: Setup firewall")
    await fw.initialize()
    await fw.setup_masquerade()
    await fw.setup_forwarding_rules()

    # Step 3: Add first client
    print("Step 3: Add client 1")
    await pm.add_peer(
        public_key="$client1_key",
        allowed_ips="10.99.99.10/32"
    )

    # Step 4: Add second client
    print("Step 4: Add client 2")
    await pm.add_peer(
        public_key="$client2_key",
        allowed_ips="10.99.99.11/32"
    )

    # Step 5: Check status
    print("Step 5: Check status")
    full_status = await status.get_full_status()
    print(f"  Interface up: {full_status.get('is_up')}")
    print(f"  Peer count: {full_status.get('peer_count', 0)}")

    # Step 6: Get peer stats
    print("Step 6: Get peer stats")
    peer_stats = await stats.get_all_stats()
    print(f"  Total peers: {peer_stats['summary']['total_peers']}")

    # Step 7: Sync peers (remove client1, keep client2)
    print("Step 7: Sync peers (remove client1)")
    sync_result = await pm.sync_peers([
        {"public_key": "$client2_key", "allowed_ips": "10.99.99.11/32"}
    ])
    print(f"  Added: {sync_result['added']}, Removed: {sync_result['removed']}")

    # Step 8: Verify final state
    print("Step 8: Verify final state")
    final_count = await pm.get_peer_count()
    print(f"  Final peer count: {final_count}")

    # Cleanup
    print("Step 9: Cleanup")
    await pm.sync_peers([])
    await fw.clear_acl_rules()

    print("=== E2E Test Complete ===")

    # Validate results
    return final_count == 1

result = asyncio.run(e2e_test())
exit(0 if result else 1)
EOF
    if [[ $? -eq 0 ]]; then
        log_success "E2E scenario passed"
    else
        log_fail "E2E scenario failed"
    fi

    # Cleanup
    wg-quick down "$TEST_CONFIG_DIR/$TEST_INTERFACE.conf" 2>/dev/null || true

    cd - > /dev/null
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  Zero Trust Hub Agent Test Suite"
    echo "=============================================="
    echo ""

    # Pre-flight checks
    check_root
    check_dependencies

    # Setup
    trap cleanup EXIT
    setup_test_env

    # Run tests
    test_python_syntax
    test_python_imports
    test_wireguard_manager
    test_peer_manager
    test_firewall_iptables
    test_ip_forwarding
    test_status_collectors
    test_command_executor
    test_websocket_handler
    test_hub_agent_integration
    test_e2e_scenario

    # Summary
    log_section "Test Summary"
    echo ""
    echo -e "  ${GREEN}Passed:${NC}  $TESTS_PASSED"
    echo -e "  ${RED}Failed:${NC}  $TESTS_FAILED"
    echo -e "  ${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
    echo ""

    local total=$((TESTS_PASSED + TESTS_FAILED))
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        exit 1
    fi
}

# Run main
main "$@"
