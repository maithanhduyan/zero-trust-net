#!/usr/bin/env python3
"""
Simple Hub Agent Test Suite
Tests all components without requiring root or actual WireGuard interface
"""

import sys
import asyncio
from pathlib import Path

# Add hub agent to path
HUB_AGENT_DIR = Path(__file__).parent.parent.parent.parent / "agent" / "hub"
sys.path.insert(0, str(HUB_AGENT_DIR))

# Colors for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

tests_passed = 0
tests_failed = 0


def log_pass(msg: str):
    global tests_passed
    print(f"{GREEN}[PASS]{RESET} {msg}")
    tests_passed += 1


def log_fail(msg: str, error: str = ""):
    global tests_failed
    print(f"{RED}[FAIL]{RESET} {msg}")
    if error:
        print(f"       Error: {error}")
    tests_failed += 1


def log_section(title: str):
    print(f"\n{BLUE}{'='*50}")
    print(f" {title}")
    print(f"{'='*50}{RESET}")


# =============================================================================
# Import Tests
# =============================================================================

def test_imports():
    log_section("Import Tests")

    modules = [
        ("wireguard.manager", "WireGuardManager"),
        ("wireguard.peer_manager", "PeerManager"),
        ("firewall.iptables", "HubFirewall"),
        ("firewall.forwarding", "ForwardingManager"),
        ("status.interface_status", "InterfaceStatus"),
        ("status.peer_stats", "PeerStats"),
        ("command_executor", "CommandExecutor"),
        ("websocket_handler", "WebSocketHandler"),
        ("hub_agent", "HubAgent"),
    ]

    for module, class_name in modules:
        try:
            mod = __import__(module, fromlist=[class_name])
            cls = getattr(mod, class_name)
            log_pass(f"Import {module}.{class_name}")
        except Exception as e:
            log_fail(f"Import {module}.{class_name}", str(e))


# =============================================================================
# Component Initialization Tests
# =============================================================================

def test_component_init():
    log_section("Component Initialization Tests")

    # WireGuardManager
    try:
        from wireguard.manager import WireGuardManager
        wg = WireGuardManager()
        assert wg.interface == "wg0"
        assert wg.config_dir == Path("/etc/wireguard")
        log_pass("WireGuardManager initialization")
    except Exception as e:
        log_fail("WireGuardManager initialization", str(e))

    # WireGuardManager with custom params
    try:
        from wireguard.manager import WireGuardManager
        wg = WireGuardManager(interface="wg-test", config_dir="/tmp/wg")
        assert wg.interface == "wg-test"
        assert wg.config_dir == Path("/tmp/wg")
        log_pass("WireGuardManager custom params")
    except Exception as e:
        log_fail("WireGuardManager custom params", str(e))

    # PeerManager
    try:
        from wireguard.manager import WireGuardManager
        from wireguard.peer_manager import PeerManager
        wg = WireGuardManager()
        pm = PeerManager(wg)
        assert pm.wg_manager is wg
        log_pass("PeerManager initialization")
    except Exception as e:
        log_fail("PeerManager initialization", str(e))

    # HubFirewall
    try:
        from firewall.iptables import HubFirewall
        fw = HubFirewall()
        assert fw.interface == "wg0"
        assert HubFirewall.FORWARD_CHAIN == "ZT_HUB_FORWARD"
        assert HubFirewall.NAT_CHAIN == "ZT_HUB_NAT"
        log_pass("HubFirewall initialization")
    except Exception as e:
        log_fail("HubFirewall initialization", str(e))

    # ForwardingManager
    try:
        from firewall.forwarding import ForwardingManager
        fwd = ForwardingManager()
        log_pass("ForwardingManager initialization")
    except Exception as e:
        log_fail("ForwardingManager initialization", str(e))

    # InterfaceStatus
    try:
        from status.interface_status import InterfaceStatus
        status = InterfaceStatus()
        assert status.interface == "wg0"
        log_pass("InterfaceStatus initialization")
    except Exception as e:
        log_fail("InterfaceStatus initialization", str(e))

    # PeerStats
    try:
        from status.peer_stats import PeerStats
        stats = PeerStats()
        log_pass("PeerStats initialization")
    except Exception as e:
        log_fail("PeerStats initialization", str(e))


# =============================================================================
# Command Executor Tests
# =============================================================================

def test_command_executor():
    log_section("CommandExecutor Tests")

    try:
        from command_executor import CommandExecutor
        from wireguard.manager import WireGuardManager
        from wireguard.peer_manager import PeerManager
        from firewall.iptables import HubFirewall
        from firewall.forwarding import ForwardingManager
        from status.interface_status import InterfaceStatus
        from status.peer_stats import PeerStats

        wg = WireGuardManager()
        pm = PeerManager(wg)
        fw = HubFirewall()
        fwd = ForwardingManager()
        status = InterfaceStatus()
        peers = PeerStats()

        executor = CommandExecutor(pm, fw, fwd, status, peers)

        # Check registered handlers
        expected_commands = [
            'add_peer', 'remove_peer', 'update_peer', 'sync_peers',
            'get_status', 'get_peer_stats', 'restart_interface', 'ping'
        ]

        for cmd in expected_commands:
            assert cmd in executor._handlers, f"Missing handler: {cmd}"

        log_pass("CommandExecutor handlers registered")

    except Exception as e:
        log_fail("CommandExecutor initialization", str(e))


# =============================================================================
# Async Command Tests
# =============================================================================

async def test_async_commands():
    log_section("Async Command Execution Tests")

    from command_executor import CommandExecutor
    from wireguard.manager import WireGuardManager
    from wireguard.peer_manager import PeerManager
    from firewall.iptables import HubFirewall
    from firewall.forwarding import ForwardingManager
    from status.interface_status import InterfaceStatus
    from status.peer_stats import PeerStats

    wg = WireGuardManager()
    pm = PeerManager(wg)
    fw = HubFirewall()
    fwd = ForwardingManager()
    status = InterfaceStatus()
    peers = PeerStats()
    executor = CommandExecutor(pm, fw, fwd, status, peers)

    # Test ping command
    try:
        result = await executor.execute('ping', {})
        assert result.get('success') is True
        assert result.get('data', {}).get('pong') is True
        log_pass("Command: ping")
    except Exception as e:
        log_fail("Command: ping", str(e))

    # Test get_status command (may fail without interface, but should not throw)
    try:
        result = await executor.execute('get_status', {})
        assert 'success' in result
        log_pass("Command: get_status")
    except Exception as e:
        log_fail("Command: get_status", str(e))

    # Test get_peer_stats command
    try:
        result = await executor.execute('get_peer_stats', {})
        assert 'success' in result
        log_pass("Command: get_peer_stats")
    except Exception as e:
        log_fail("Command: get_peer_stats", str(e))

    # Test unknown command
    try:
        result = await executor.execute('unknown_command', {})
        assert result.get('success') is False
        assert 'Unknown command' in result.get('error', '')
        log_pass("Command: unknown_command (correctly rejected)")
    except Exception as e:
        log_fail("Command: unknown_command", str(e))


# =============================================================================
# WebSocket Handler Tests
# =============================================================================

def test_websocket_handler():
    log_section("WebSocketHandler Tests")

    try:
        from websocket_handler import WebSocketHandler
        from command_executor import CommandExecutor
        from wireguard.manager import WireGuardManager
        from wireguard.peer_manager import PeerManager
        from firewall.iptables import HubFirewall
        from firewall.forwarding import ForwardingManager
        from status.interface_status import InterfaceStatus
        from status.peer_stats import PeerStats

        wg = WireGuardManager()
        pm = PeerManager(wg)
        fw = HubFirewall()
        fwd = ForwardingManager()
        status = InterfaceStatus()
        peers = PeerStats()
        executor = CommandExecutor(pm, fw, fwd, status, peers)

        ws = WebSocketHandler(
            url='ws://localhost:8000/api/v1/ws/hub',
            api_key='test-api-key',
            command_executor=executor
        )

        assert ws.url == 'ws://localhost:8000/api/v1/ws/hub'
        assert ws.api_key == 'test-api-key'
        assert ws.reconnect_delay == 1.0
        assert ws.max_reconnect_delay == 60.0
        assert ws.ping_interval == 30.0
        log_pass("WebSocketHandler initialization")

    except Exception as e:
        log_fail("WebSocketHandler initialization", str(e))

    # Test custom params
    try:
        ws = WebSocketHandler(
            url='ws://example.com/ws',
            api_key='key123',
            command_executor=executor,
            reconnect_delay=2.0,
            max_reconnect_delay=120.0,
            ping_interval=60.0
        )
        assert ws.reconnect_delay == 2.0
        assert ws.max_reconnect_delay == 120.0
        assert ws.ping_interval == 60.0
        log_pass("WebSocketHandler custom params")
    except Exception as e:
        log_fail("WebSocketHandler custom params", str(e))


# =============================================================================
# HubAgent Tests
# =============================================================================

def test_hub_agent():
    log_section("HubAgent Tests")

    try:
        from hub_agent import HubAgent

        agent = HubAgent(
            control_plane_url='ws://localhost:8000/api/v1/ws/hub',
            api_key='test-key-123',
            interface='wg0'
        )

        assert agent.control_plane_url == 'ws://localhost:8000/api/v1/ws/hub'
        assert agent.api_key == 'test-key-123'
        assert agent.interface == 'wg0'
        assert agent.config_dir == Path('/etc/wireguard')
        log_pass("HubAgent initialization")

    except Exception as e:
        log_fail("HubAgent initialization", str(e))

    # Test with custom params
    try:
        from hub_agent import HubAgent

        agent = HubAgent(
            control_plane_url='ws://192.168.1.1:8000/ws',
            api_key='custom-key',
            interface='wg-custom',
            config_dir='/custom/wireguard',
            status_interval=60
        )

        assert agent.interface == 'wg-custom'
        assert agent.config_dir == Path('/custom/wireguard')
        assert agent.status_interval == 60
        log_pass("HubAgent custom params")

    except Exception as e:
        log_fail("HubAgent custom params", str(e))

    # Test components are created
    try:
        from hub_agent import HubAgent

        agent = HubAgent(
            control_plane_url='ws://localhost:8000/api/v1/ws/hub',
            api_key='test-key'
        )

        assert agent.wg_manager is not None
        assert agent.peer_manager is not None
        assert agent.firewall is not None
        assert agent.forwarding is not None
        assert agent.interface_status is not None
        assert agent.peer_stats is not None
        log_pass("HubAgent components created")

    except Exception as e:
        log_fail("HubAgent components created", str(e))


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"\n{BLUE}{'='*50}")
    print(" Zero Trust Hub Agent Test Suite")
    print(f"{'='*50}{RESET}\n")

    print(f"Hub Agent Directory: {HUB_AGENT_DIR}")
    print(f"Python Version: {sys.version.split()[0]}")

    # Run tests
    test_imports()
    test_component_init()
    test_command_executor()
    asyncio.run(test_async_commands())
    test_websocket_handler()
    test_hub_agent()

    # Summary
    print(f"\n{BLUE}{'='*50}")
    print(" Test Summary")
    print(f"{'='*50}{RESET}")
    print(f"{GREEN}Passed: {tests_passed}{RESET}")
    print(f"{RED}Failed: {tests_failed}{RESET}")

    total = tests_passed + tests_failed
    if tests_failed == 0:
        print(f"\n{GREEN}✅ All {total} tests passed!{RESET}\n")
        return 0
    else:
        print(f"\n{RED}❌ {tests_failed}/{total} tests failed{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
