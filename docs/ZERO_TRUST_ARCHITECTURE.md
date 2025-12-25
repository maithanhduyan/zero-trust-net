# Zero Trust Network Architecture - Enterprise Grade

## 🎯 Nguyên tắc Zero Trust

```
"Never Trust, Always Verify" - Không bao giờ tin tưởng, luôn xác minh
```

### 5 Trụ cột Zero Trust:

| # | Trụ cột | Mô tả | Triển khai |
|---|---------|-------|------------|
| 1 | **Identity** | Xác thực danh tính | WireGuard Keys + SSH Keys |
| 2 | **Device** | Tin cậy thiết bị | WireGuard Peer Verification |
| 3 | **Network** | Phân đoạn mạng | Microsegmentation + Firewall |
| 4 | **Application** | Bảo vệ ứng dụng | mTLS + Service Mesh |
| 5 | **Data** | Mã hóa dữ liệu | Encryption at Rest & Transit |

---

## 🏗️ Kiến trúc tổng quan

```
                                    INTERNET
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
              ┌─────────┐        ┌─────────┐        ┌─────────┐
              │ EDGE-1  │        │ EDGE-2  │        │ EDGE-3  │
              │(EU/US/AP)│       │(EU/US/AP)│       │(EU/US/AP)│
              └────┬────┘        └────┬────┘        └────┬────┘
                   │                  │                  │
                   └──────────────────┼──────────────────┘
                                      │
                    ══════════════════╪══════════════════
                    ║   WIREGUARD ENCRYPTED MESH      ║
                    ══════════════════╪══════════════════
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
   ┌───────────┐               ┌───────────┐               ┌───────────┐
   │  CONTROL  │               │  DATABASE │               │APPLICATION│
   │   PLANE   │               │   TIER    │               │   TIER    │
   │           │               │           │               │           │
   │ • Hub-1   │ ◄──────────► │ • Primary │ ◄──────────► │ • Odoo-1  │
   │ • Hub-2   │    VXLAN     │ • Replica │    VXLAN     │ • Odoo-2  │
   │ • Vault   │               │ • Arbiter │               │ • HAProxy │
   └───────────┘               └───────────┘               └───────────┘
   10.10.0.1-9                 10.10.0.10-19               10.10.0.20-29
```

---

## 🔐 Layer 1: Network Security

### 1.1 WireGuard Mesh (Đã triển khai ✅)

```
┌─────────────────────────────────────────────────────────────────┐
│                     WIREGUARD MESH NETWORK                       │
│                                                                  │
│    Hub-1 ◄────────────────────────────────────────► Hub-2       │
│   (10.10.0.1)                                    (10.10.0.2)    │
│       ▲                                               ▲         │
│       │                                               │         │
│       ├───────────────┬───────────────────────────────┤         │
│       │               │                               │         │
│       ▼               ▼                               ▼         │
│  db-primary      db-replica                      (future)       │
│  (10.10.0.10)    (10.10.0.11)                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Microsegmentation với iptables/nftables

```bash
# Database Tier - Chỉ cho phép:
# - PostgreSQL (5432) từ App Tier
# - Replication (5432) từ DB Tier
# - SSH (22) từ Control Plane

# Application Tier - Chỉ cho phép:
# - HTTP/HTTPS (80/443) từ Edge
# - SSH (22) từ Control Plane
# - DB connection (5432) đến DB Tier

# Control Plane - Full access cho quản trị
```

### 1.3 Firewall Zones

| Zone | Subnet | Allowed Inbound | Allowed Outbound |
|------|--------|-----------------|------------------|
| CONTROL | 10.10.0.1-9 | SSH, WireGuard | ALL |
| DATABASE | 10.10.0.10-19 | PostgreSQL (từ APP) | Replication, Updates |
| APPLICATION | 10.10.0.20-29 | HTTP/HTTPS | DB, External APIs |
| MONITORING | 10.10.0.30-39 | Metrics | ALL (read-only) |

---

## 🔑 Layer 2: Identity & Access

### 2.1 WireGuard Key Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    KEY MANAGEMENT FLOW                           │
│                                                                  │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐               │
│  │ Generate │ ───► │ Encrypt  │ ───► │  Store   │               │
│  │   Keys   │      │(Age/SOPS)│      │(Ansible  │               │
│  │          │      │          │      │  Vault)  │               │
│  └──────────┘      └──────────┘      └──────────┘               │
│       │                                    │                     │
│       │            ┌──────────┐            │                     │
│       └──────────► │ Distribute│ ◄─────────┘                     │
│                    │ via Ansible│                                │
│                    └──────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 SSH Access Control

| Role | Nodes Accessible | Method |
|------|------------------|--------|
| Admin | ALL | SSH Key + WireGuard |
| Developer | App nodes only | SSH Key + WireGuard |
| DBA | DB nodes only | SSH Key + WireGuard |
| Monitoring | Read-only metrics | API Token |

### 2.3 Ansible Vault for Secrets

```yaml
# Encrypted secrets (ansible-vault)
vault_wireguard_private_keys:
  hub-1: !vault |
    $ANSIBLE_VAULT;1.1;AES256
    ...encrypted...
  db-primary: !vault |
    $ANSIBLE_VAULT;1.1;AES256
    ...encrypted...

vault_postgres_passwords:
  replication: !vault |
    ...encrypted...
  admin: !vault |
    ...encrypted...
```

---

## 🛡️ Layer 3: Defense in Depth

### 3.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 7: Application Security (WAF, Input Validation)          │
├─────────────────────────────────────────────────────────────────┤
│ Layer 6: Service Authentication (mTLS, JWT)                     │
├─────────────────────────────────────────────────────────────────┤
│ Layer 5: Container Security (Rootless, AppArmor, Seccomp)       │
├─────────────────────────────────────────────────────────────────┤
│ Layer 4: Host Security (SSH Hardening, Fail2ban)                │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Network Security (WireGuard Encryption)                │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Firewall (iptables/nftables Microsegmentation)         │
├─────────────────────────────────────────────────────────────────┤
│ Layer 1: Physical/Cloud Security (VPS Provider)                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Security Controls per Layer

| Layer | Control | Tool | Status |
|-------|---------|------|--------|
| Network | Encryption | WireGuard | ✅ Done |
| Network | Segmentation | iptables/nftables | 🔄 Pending |
| Host | SSH Lockdown | Ansible playbook | 🔄 Pending |
| Host | Intrusion Detection | Fail2ban | 🔄 Pending |
| Host | Audit Logging | auditd | 🔄 Pending |
| Container | Rootless | Docker rootless | 🔄 Pending |
| Container | Resource Limits | cgroups | 🔄 Pending |
| Application | mTLS | Traefik/Envoy | 🔄 Pending |

---

## 📊 Layer 4: Monitoring & Observability

### 4.1 Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    MONITORING ARCHITECTURE                       │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   Metrics   │    │    Logs     │    │   Traces    │          │
│  │ (Prometheus)│    │   (Loki)    │    │  (Jaeger)   │          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │   Grafana     │                            │
│                    │  Dashboard    │                            │
│                    └───────────────┘                            │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Alerting   │    │   Audit     │    │  Security   │          │
│  │(Alertmanager)│   │  (auditd)   │    │  (Wazuh)    │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Key Metrics to Monitor

| Category | Metric | Alert Threshold |
|----------|--------|-----------------|
| Network | WireGuard handshake age | > 5 minutes |
| Network | Packet loss | > 1% |
| Security | Failed SSH attempts | > 5/minute |
| Security | Unauthorized connection attempts | Any |
| Database | Replication lag | > 10 seconds |
| Database | Connection pool usage | > 80% |
| Application | Response time | > 500ms |
| Application | Error rate | > 1% |

---

## 🔄 Layer 5: High Availability

### 5.1 HA Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIGH AVAILABILITY DESIGN                      │
│                                                                  │
│                       ┌─────────┐                               │
│                       │   VIP   │                               │
│                       │10.10.0.100│                             │
│                       └────┬────┘                               │
│                            │                                     │
│               ┌────────────┼────────────┐                       │
│               │            │            │                       │
│               ▼            │            ▼                       │
│         ┌─────────┐        │      ┌─────────┐                   │
│         │  Hub-1  │◄─Keepalived─►│  Hub-2  │                   │
│         │ MASTER  │        │      │ BACKUP  │                   │
│         └─────────┘        │      └─────────┘                   │
│                            │                                     │
│  ┌─────────────────────────┼─────────────────────────┐          │
│  │                         │                         │          │
│  ▼                         ▼                         ▼          │
│ ┌──────────┐         ┌──────────┐             ┌──────────┐      │
│ │PostgreSQL│◄─Patroni─►│PostgreSQL│           │PostgreSQL│      │
│ │ Leader   │         │ Replica  │             │ Arbiter  │      │
│ └──────────┘         └──────────┘             └──────────┘      │
│                                                                  │
│ ┌──────────┐         ┌──────────┐                               │
│ │  Odoo-1  │◄─HAProxy─►│  Odoo-2  │                             │
│ └──────────┘         └──────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Failover Scenarios

| Component | Failure | Recovery | RTO |
|-----------|---------|----------|-----|
| Hub-1 | Network outage | Keepalived VIP failover | < 3s |
| DB Primary | Crash | Patroni auto-failover | < 30s |
| Odoo-1 | Application error | HAProxy health check | < 5s |
| WireGuard | Tunnel down | Peer reconnect | < 60s |

---

## 📋 Implementation Roadmap

### Phase 1: Foundation (Week 1) ✅ DONE
- [x] WireGuard mesh setup
- [x] Control Plane (Hub-1, Hub-2)
- [x] Worker nodes (db-primary, db-replica)
- [x] Ansible inventory structure

### Phase 2: Security Hardening (Week 2) 🔄 IN PROGRESS
- [ ] SSH lockdown (WireGuard only)
- [ ] Microsegmentation (iptables rules)
- [ ] Fail2ban installation
- [ ] Audit logging (auditd)

### Phase 3: High Availability (Week 3)
- [ ] Full Mesh P2P connections
- [ ] Keepalived for VIP failover
- [ ] PostgreSQL HA with Patroni
- [ ] Multi-Hub worker connections

### Phase 4: Application Layer (Week 4)
- [ ] Docker deployment
- [ ] Odoo application
- [ ] HAProxy load balancer
- [ ] mTLS between services

### Phase 5: Monitoring (Week 5)
- [ ] Prometheus + Grafana
- [ ] Loki for logs
- [ ] Alertmanager
- [ ] Security dashboards

### Phase 6: Compliance & Audit (Week 6)
- [ ] Security policy documentation
- [ ] Compliance checks
- [ ] Penetration testing
- [ ] Disaster recovery testing

---

## 🚀 Quick Start Commands

```bash
# 1. Security Hardening
ansible-playbook playbooks/security-hardening.yml

# 2. Full Mesh P2P
ansible-playbook playbooks/setup-full-mesh.yml

# 3. SSH Lockdown (CAUTION!)
ansible-playbook playbooks/lockdown-ssh.yml

# 4. Deploy PostgreSQL HA
ansible-playbook playbooks/deploy-postgres-ha.yml

# 5. Deploy Application
ansible-playbook playbooks/deploy-odoo.yml
```

---

## 📁 Project Structure

```
/home/zero-trust-netwoking/
├── ansible.cfg                 # Ansible configuration
├── inventory/
│   ├── hosts.ini              # Node inventory (secrets - not in git)
│   ├── hosts.ini.example      # Template (safe for git)
│   └── group_vars/
│       ├── all.yml            # Global variables
│       ├── control_plane.yml  # Hub settings
│       ├── db_nodes.yml       # Database settings
│       └── app_nodes.yml      # Application settings
├── playbooks/
│   ├── site.yml               # Master playbook
│   ├── setup-control-plane.yml
│   ├── deploy-worker-nodes.yml
│   ├── setup-full-mesh.yml
│   ├── lockdown-ssh.yml
│   ├── security-hardening.yml # NEW
│   ├── deploy-postgres-ha.yml # NEW
│   └── deploy-odoo.yml        # NEW
├── roles/
│   ├── common/                # Base configuration
│   ├── security/              # Security hardening
│   ├── wireguard/             # VPN mesh
│   ├── docker/                # Container runtime
│   ├── postgres-ha/           # Database HA
│   └── odoo-app/              # Application
├── scripts/
│   ├── add-node.sh            # Add new node to mesh
│   ├── backup-config.sh       # Backup all configs
│   └── health-check.sh        # Check mesh health
└── docs/
    ├── README.MD
    ├── ZERO_TRUST_ARCHITECTURE.md  # This file
    ├── HIGH_AVAILABILITY.md
    └── WIREGUARD_MESH.md
```

---

## 🔒 Security Checklist

### Network Security
- [ ] All traffic encrypted via WireGuard
- [ ] SSH accessible only via WireGuard IPs
- [ ] Firewall rules per security zone
- [ ] No public ports except WireGuard (51820/UDP)

### Host Security
- [ ] SSH key-only authentication
- [ ] Root login via SSH disabled
- [ ] Fail2ban active
- [ ] Automatic security updates
- [ ] Audit logging enabled

### Container Security
- [ ] Rootless Docker
- [ ] Read-only filesystems where possible
- [ ] Resource limits (CPU, memory)
- [ ] No privileged containers
- [ ] Image scanning

### Application Security
- [ ] mTLS between services
- [ ] Secrets in Ansible Vault
- [ ] Regular password rotation
- [ ] Input validation
- [ ] Rate limiting

---

## 📞 Emergency Procedures

### WireGuard Tunnel Down
```bash
# On affected node
wg show                          # Check status
systemctl restart wg-quick@wg0   # Restart tunnel
ping 10.10.0.1                   # Test connectivity
```

### Node Unreachable
```bash
# From control machine
./scripts/health-check.sh        # Check all nodes
ssh -o ConnectTimeout=5 root@<public_ip>  # Direct SSH (if lockdown not applied)
```

### Database Failover
```bash
# Check Patroni status
patronictl -c /etc/patroni/config.yml list

# Manual failover (if needed)
patronictl -c /etc/patroni/config.yml failover
```

---

**Last Updated:** 2024-12-25
**Version:** 1.0.0
**Author:** Zero Trust Network Team
