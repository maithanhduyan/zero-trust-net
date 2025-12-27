# Agent Test Cases
# Zero Trust Network Agent Testing Documentation

## Test Categories

### 1. Unit Tests
| ID | Component | Test Case | Expected Result |
|----|-----------|-----------|-----------------|
| U01 | client.py | `has_interface("lo")` | Returns `True` |
| U02 | client.py | `has_interface("nonexistent")` | Returns `False` |
| U03 | client.py | `get_base_url()` without wg0 | Returns env or default URL |
| U04 | client.py | `ControlPlaneClient` init | Client created with correct URL |
| U05 | host_info.py | `collect_host_info()` | Returns dict with hostname, os_info |
| U06 | host_info.py | `collect_resource_usage()` | Returns dict with memory_percent |
| U07 | config_builder.py | `build_config()` | Returns valid WireGuard config string |
| U08 | config_builder.py | `parse_config()` | Parses INI format correctly |

### 2. Integration Tests (requires Control Plane running)
| ID | Component | Test Case | Expected Result |
|----|-----------|-----------|-----------------|
| I01 | client.py | `register()` new node | Returns overlay_ip, status=pending |
| I02 | client.py | `register()` existing node | Returns 409 or updates node |
| I03 | client.py | `get_config()` active node | Returns peers, acl_rules |
| I04 | client.py | `get_config()` pending node | Returns 403 Forbidden |
| I05 | client.py | `heartbeat()` | Returns config_changed flag |
| I06 | client.py | `get_status()` | Returns node status |

### 3. WireGuard Tests (requires root)
| ID | Component | Test Case | Expected Result |
|----|-----------|-----------|-----------------|
| W01 | manager.py | `is_installed()` | Returns True if wg command exists |
| W02 | manager.py | `generate_keypair()` | Creates private.key, public.key |
| W03 | manager.py | `get_public_key()` | Returns 44-char base64 string |
| W04 | manager.py | `keypair_exists()` | Returns True after generation |
| W05 | config_builder.py | `write_config()` | Creates file with 0600 permissions |

### 4. Firewall Tests (requires root)
| ID | Component | Test Case | Expected Result |
|----|-----------|-----------|-----------------|
| F01 | iptables.py | `_ensure_chain_exists()` | ZT_ACL chain created |
| F02 | iptables.py | `apply_rules([])` | Flushes chain, adds default deny |
| F03 | iptables.py | `apply_rules([allow_rule])` | Rule added with ACCEPT target |
| F04 | iptables.py | `list_rules()` | Returns iptables -L output |
| F05 | iptables.py | `cleanup()` | Removes ZT_ACL chain |

### 5. End-to-End Tests
| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| E01 | Fresh registration | 1. Start agent<br>2. Agent registers<br>3. Check status | Node appears in Control Plane with pending status |
| E02 | Config sync | 1. Approve node in Control Plane<br>2. Wait for sync<br>3. Check WireGuard | Peers configured correctly |
| E03 | Policy enforcement | 1. Add policy in Control Plane<br>2. Wait for sync<br>3. Check iptables | ACL rule appears in ZT_ACL chain |
| E04 | Graceful shutdown | 1. Send SIGTERM to agent<br>2. Check logs | Agent logs shutdown message, exits cleanly |
| E05 | Reconnection | 1. Stop Control Plane<br>2. Agent retries<br>3. Start Control Plane | Agent reconnects and syncs |

### 6. Error Handling Tests
| ID | Scenario | Test Case | Expected Result |
|----|----------|-----------|-----------------|
| H01 | Network error | Control Plane unreachable | Agent logs error, retries |
| H02 | Invalid response | Malformed JSON response | Agent handles gracefully |
| H03 | Auth error | 403 Forbidden | Agent waits for approval |
| H04 | Timeout | Slow Control Plane | Request times out, retries |

---

## Test Environment Setup

### Prerequisites
```bash
# 1. Control Plane running
cd control-plane && uv run uvicorn main:app --port 8000

# 2. Python environment for agent
cd agent && python3 -m venv .venv && source .venv/bin/activate

# 3. Root access for WireGuard/iptables tests
sudo -v
```

### Environment Variables
```bash
export CONTROL_PLANE_URL="http://localhost:8000"
export TEST_HOSTNAME="test-agent-01"
export TEST_ROLE="app"
```

---

## Test Execution

### Run all tests
```bash
./tests/agent/agent_test.sh
```

### Run specific category
```bash
./tests/agent/agent_test.sh unit
./tests/agent/agent_test.sh integration
./tests/agent/agent_test.sh wireguard
./tests/agent/agent_test.sh firewall
./tests/agent/agent_test.sh e2e
```

---

## Success Criteria

| Category | Pass Criteria |
|----------|---------------|
| Unit Tests | 100% pass |
| Integration Tests | 100% pass (with Control Plane) |
| WireGuard Tests | 100% pass (with root) |
| Firewall Tests | 100% pass (with root) |
| E2E Tests | 100% pass (full environment) |
