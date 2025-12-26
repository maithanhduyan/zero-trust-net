# Zero Trust Network - Workflow Design

## Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ZERO TRUST NETWORK WORKFLOW                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   ADMIN     │───▶│  CONTROL PLANE  │◀───│         POLICY FILES            │ │
│  │  (Ansible)  │    │   (FastAPI)     │    │  policies/*.yaml                │ │
│  └─────────────┘    └────────┬────────┘    └─────────────────────────────────┘ │
│                              │                                                  │
│                              │ HTTPS/WireGuard                                  │
│                              ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         VPS NODES (Agents)                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │   VPS-1      │  │   VPS-2      │  │   VPS-3      │  │   VPS-4      │ │  │
│  │  │   Hub        │  │   App        │  │   DB         │  │   Ops        │ │  │
│  │  │  10.0.0.1    │  │  10.0.0.2    │  │  10.0.0.3    │  │  10.0.0.4    │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  │         │                 │                 │                 │         │  │
│  │         └─────────────────┴─────────────────┴─────────────────┘         │  │
│  │                          WireGuard Mesh (wg0)                            │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Luồng hoạt động chính

### Phase 1: Bootstrap Hub (VPS-1)

```bash
# 1. Admin chạy playbook trên VPS-1
ansible-playbook -i inventory/hosts.ini playbook/setup-hub.yml

# Kết quả:
# - Cài đặt Control Plane (FastAPI)
# - Cài đặt WireGuard (Hub mode)
# - Generate Hub keypair
# - Khởi động services
```

### Phase 2: Deploy Agents (VPS-2, VPS-3, ...)

```bash
# 2. Admin chạy playbook để deploy agents
ansible-playbook -i inventory/hosts.ini playbook/deploy-agents.yml

# Mỗi Agent sẽ:
# 1. Cài đặt WireGuard
# 2. Generate keypair
# 3. Gọi API /register để lấy Overlay IP
# 4. Cấu hình wg0.conf
# 5. Kết nối vào Hub
# 6. Chạy agent daemon
```

### Phase 3: Agent Sync Loop (Continuous)

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT SYNC LOOP                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐                         ┌─────────────────┐   │
│  │   Agent     │  1. GET /config         │  Control Plane  │   │
│  │   Daemon    │────────────────────────▶│                 │   │
│  │             │                         │                 │   │
│  │             │  2. Return config       │                 │   │
│  │             │◀────────────────────────│                 │   │
│  │             │     - peers[]           │                 │   │
│  │             │     - acl_rules[]       │                 │   │
│  │             │     - config_version    │                 │   │
│  └──────┬──────┘                         └─────────────────┘   │
│         │                                                       │
│         │ 3. Apply config                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Update /etc/wireguard/wg0.conf (if peers changed)   │   │
│  │  - Apply iptables rules (Zero Trust ACLs)              │   │
│  │  - Restart wg0 if needed                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Loop every 60 seconds                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Chi tiết các thành phần

### 1. Control Plane API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agent/register` | POST | Agent đăng ký lần đầu, nhận Overlay IP |
| `/api/v1/agent/config/{hostname}` | GET | Agent lấy config (peers + ACL) |
| `/api/v1/agent/heartbeat` | POST | Agent gửi heartbeat |
| `/api/v1/admin/nodes` | GET | Admin liệt kê nodes |
| `/api/v1/admin/nodes/{id}/approve` | POST | Admin duyệt node |
| `/api/v1/admin/policies` | GET/POST | Quản lý policies |

### 2. Agent Components

```
agent/
├── agent.py              # Main daemon
├── client.py             # HTTP client to Control Plane
├── collectors/
│   ├── host_info.py      # Thu thập thông tin host
│   └── network_stats.py  # Thu thập metrics
├── firewall/
│   ├── iptables.py       # Apply iptables rules
│   └── nftables.py       # Apply nftables rules
└── wireguard/
    ├── config_builder.py # Generate wg0.conf
    └── manager.py        # Manage WireGuard interface
```

### 3. Policy Files

```yaml
# policies/global.yaml
version: "1.0"
default_action: DROP
logging: true

# policies/roles/app.yaml
role: app
outbound:
  - to: db
    ports: [5432]
    protocol: tcp
  - to: hub
    ports: [51820]
    protocol: udp
inbound:
  - from: ops
    ports: [22]
    protocol: tcp
```

---

## Deployment Sequence

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT SEQUENCE                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Step 1: Prepare                                                           │
│  ─────────────────                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  $ cp .env.example .env                                             │  │
│  │  $ vim .env  # Configure HUB_PUBLIC_KEY, HUB_ENDPOINT               │  │
│  │  $ vim infrastructure/ansible/inventory/hosts.ini                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Step 2: Deploy Hub (VPS-1)                                                │
│  ────────────────────────────                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  $ ansible-playbook -i inventory/hosts.ini playbook/setup-hub.yml  │  │
│  │                                                                      │  │
│  │  Result:                                                             │  │
│  │  - WireGuard Hub @ 10.0.0.1                                         │  │
│  │  - Control Plane API @ :8000                                        │  │
│  │  - PostgreSQL @ :5432                                               │  │
│  │  - Caddy reverse proxy @ :443                                       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Step 3: Sync Policies                                                     │
│  ─────────────────────                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  $ ansible-playbook -i inventory/hosts.ini playbook/sync-policies.yml│ │
│  │                                                                      │  │
│  │  Result:                                                             │  │
│  │  - policies/*.yaml → Control Plane DB                               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Step 4: Deploy Agents (All other VPS)                                     │
│  ──────────────────────────────────────                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  $ ansible-playbook -i inventory/hosts.ini playbook/deploy-agents.yml│ │
│  │                                                                      │  │
│  │  For each host:                                                      │  │
│  │  1. Install WireGuard + Agent                                        │  │
│  │  2. Generate keypair                                                 │  │
│  │  3. POST /register → Receive Overlay IP                             │  │
│  │  4. Configure wg0.conf                                               │  │
│  │  5. Start agent.service                                              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Step 5: Verify                                                            │
│  ──────────────                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  $ ansible-playbook -i inventory/hosts.ini playbook/verify.yml      │  │
│  │                                                                      │  │
│  │  - Ping all nodes via Overlay                                       │  │
│  │  - Check WireGuard handshakes                                       │  │
│  │  - Verify ACL rules                                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Zero Trust Flow Example

### Scenario: Odoo (app) connects to PostgreSQL (db)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ZERO TRUST CONNECTION: Odoo → PostgreSQL                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Odoo (10.0.0.2) wants to connect to PostgreSQL (10.0.0.3:5432)         │
│                                                                             │
│  2. Traffic flow:                                                           │
│     ┌─────────────┐                                    ┌─────────────┐     │
│     │  VPS-2      │  ─────── wg0 tunnel ──────────▶   │  VPS-3      │     │
│     │  Odoo       │                                    │  PostgreSQL │     │
│     │  10.0.0.2   │  src:10.0.0.2 dst:10.0.0.3:5432   │  10.0.0.3   │     │
│     └─────────────┘                                    └──────┬──────┘     │
│                                                               │             │
│  3. PostgreSQL node checks iptables:                          ▼             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │  # Applied by Agent from Control Plane ACL                      │    │
│     │  -A INPUT -s 10.0.0.2 -p tcp --dport 5432 -j ACCEPT             │    │
│     │  -A INPUT -p tcp --dport 5432 -j DROP  # Default deny           │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  4. Connection ALLOWED ✓ (because app→db policy exists)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Scenario: Unauthorized access attempt

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ZERO TRUST BLOCK: Random VPS → PostgreSQL                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Attacker (Internet) tries to connect to PostgreSQL                      │
│                                                                             │
│  2. BLOCKED at multiple layers:                                             │
│                                                                             │
│     Layer 1: No WireGuard peer = Cannot reach overlay network               │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │  Attacker has no WireGuard private key                          │    │
│     │  → Cannot join overlay network                                   │    │
│     │  → 10.0.0.3 is unreachable                                       │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     Layer 2: Public IP is firewalled                                        │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │  PostgreSQL binds to 10.0.0.3:5432 only (overlay IP)            │    │
│     │  Port 5432 not exposed on public interface                      │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     Layer 3: Even if inside overlay, ACL blocks                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │  No policy allows unknown-role → db                             │    │
│     │  Default action: DROP                                           │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Result: CONNECTION DENIED ✗                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
zero-trust-networking/
├── control-plane/           # FastAPI Control Plane
│   ├── main.py
│   ├── config.py
│   ├── api/v1/
│   ├── core/
│   ├── database/
│   └── schemas/
│
├── agent/                   # Agent daemon
│   ├── agent.py            # Main daemon loop
│   ├── client.py           # API client
│   ├── wireguard/          # WireGuard management
│   └── firewall/           # Firewall management
│
├── infrastructure/
│   └── ansible/
│       ├── inventory/
│       │   └── hosts.ini   # Host inventory
│       ├── playbook/
│       │   ├── setup-hub.yml
│       │   ├── deploy-agents.yml
│       │   ├── sync-policies.yml
│       │   └── verify.yml
│       └── roles/
│           ├── common/
│           ├── control-plane/
│           └── agent/
│
├── policies/                # Policy definitions
│   ├── global.yaml
│   └── roles/
│       ├── app.yaml
│       ├── database.yaml
│       └── ops.yaml
│
└── docs/
    └── WORKFLOW.md          # This file
```
