# 🔐 Zero Trust Network - Enterprise Grade

**100% Self-Hosted | No Third-Party Dependencies | Ansible + WireGuard + Docker**

```
     ╔═══════════════════════════════════════════════════════════════╗
     ║                 ZERO TRUST ARCHITECTURE                        ║
     ║                                                                 ║
     ║   "Never Trust, Always Verify" - Không tin tưởng, luôn xác minh║
     ╚═══════════════════════════════════════════════════════════════╝
```

## 🎯 Tổng quan

Dự án này xây dựng **Zero Trust Network cấp doanh nghiệp** với các tính năng:

| Feature | Technology | Status |
|---------|------------|--------|
| **VPN Mesh** | WireGuard (self-hosted) | ✅ |
| **Automation** | Ansible | ✅ |
| **Containerization** | Docker | ✅ |
| **High Availability** | Multi-Hub + Full Mesh | ✅ |
| **Security Hardening** | UFW + Fail2ban + Auditd | ✅ |
| **SSH Zero Trust** | WireGuard-only access | ✅ |

## 🏗️ Kiến trúc

```
                            INTERNET
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
         [Hub-1]◄─────────►[Hub-2]         [Future Hubs]
        10.10.0.1         10.10.0.2
              │                │
    ══════════╪════════════════╪══════════════════
    ║    WIREGUARD ENCRYPTED MESH (P2P)         ║
    ══════════╪════════════════╪══════════════════
              │                │
      ┌───────┴────────┬───────┴────────┐
      ▼                ▼                ▼
 [db-primary]    [db-replica]     [app-nodes]
  10.10.0.10      10.10.0.11      10.10.0.20+
```

### IP Scheme

| Range | Purpose | Examples |
|-------|---------|----------|
| 10.10.0.1-9 | Control Plane (Hubs) | hub-1, hub-2 |
| 10.10.0.10-19 | Database Nodes | db-primary, db-replica |
| 10.10.0.20-29 | Application Nodes | odoo-1, odoo-2 |
| 10.10.0.30-39 | Monitoring/Ops | prometheus, grafana |
| 10.10.0.100+ | Additional Nodes | - |

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Ubuntu 24.04 LTS
# Root access hoặc sudo

# Cài đặt cơ bản
./bootstrap.sh
```

### 2. Initialize Configuration

```bash
# Copy template files
cp inventory/hosts.ini.example inventory/hosts.ini
cp inventory/group_vars/all.yml.example inventory/group_vars/all.yml

# Chỉnh sửa theo môi trường của bạn
nano inventory/hosts.ini
nano inventory/group_vars/all.yml
```

### 3. Setup Control Plane (Hub)

```bash
# Cài đặt WireGuard Hub đầu tiên
ansible-playbook playbooks/setup-control-plane.yml
```

### 4. Add Worker Nodes

```bash
# Thêm node mới vào mesh (1 lệnh duy nhất)
./scripts/add-node.sh <name> <public_ip> <wg_ip> [ssh_port]

# Ví dụ:
./scripts/add-node.sh db-primary 155.133.7.195 10.10.0.10 2222
./scripts/add-node.sh db-replica 155.133.7.254 10.10.0.11 22
```

### 5. Security Hardening

```bash
# Áp dụng security hardening cấp doanh nghiệp
ansible-playbook playbooks/security-hardening.yml

# SSH Lockdown (chỉ cho phép từ WireGuard)
ansible-playbook playbooks/lockdown-ssh.yml
```

### 6. Health Check

```bash
# Kiểm tra trạng thái mesh
./scripts/health-check.sh

# Quick check (ping only)
./scripts/health-check.sh --quick
```

## 📁 Project Structure

```
/home/zero-trust-netwoking/
├── ansible.cfg                    # Ansible configuration
├── bootstrap.sh                   # Initial setup script
│
├── inventory/
│   ├── hosts.ini                  # ⚠️ SECRETS - Not in git
│   ├── hosts.ini.example          # ✅ Template - Safe for git
│   └── group_vars/
│       ├── all.yml                # ⚠️ SECRETS
│       ├── all.yml.example        # ✅ Template
│       ├── control_plane.yml      # Hub settings
│       ├── db_nodes.yml           # Database settings
│       └── app_nodes.yml          # App settings
│
├── playbooks/
│   ├── site.yml                   # Master playbook
│   ├── setup-control-plane.yml    # Setup WireGuard Hub
│   ├── deploy-worker-nodes.yml    # Deploy workers
│   ├── setup-full-mesh.yml        # P2P connections
│   ├── security-hardening.yml     # Enterprise security
│   └── lockdown-ssh.yml           # SSH via WireGuard only
│
├── roles/
│   ├── common/                    # Base configuration
│   ├── security/                  # Security hardening
│   ├── wireguard/                 # VPN mesh
│   ├── docker/                    # Container runtime
│   ├── postgres-ha/               # Database HA
│   └── odoo-app/                  # Application
│
├── scripts/
│   ├── add-node.sh                # One-click add node
│   ├── health-check.sh            # System health check
│   └── init-config.sh             # Initialize config
│
└── docs/
    ├── README.MD                  # This file
    ├── ZERO_TRUST_ARCHITECTURE.md # Full architecture
    ├── HIGH_AVAILABILITY.md       # HA documentation
    └── WIREGUARD_MESH.md          # WireGuard details
```

## 🔐 Security Features

### Layer 1: Network
- ✅ **WireGuard Encryption**: All traffic encrypted
- ✅ **Microsegmentation**: Firewall zones per node type
- ✅ **No public ports**: Only WireGuard port exposed

### Layer 2: Host
- ✅ **SSH Hardening**: Key-only auth, rate limiting
- ✅ **Fail2ban**: Auto-ban brute force attempts
- ✅ **Audit Logging**: Track all security events
- ✅ **Kernel Hardening**: Sysctl security parameters

### Layer 3: Access
- ✅ **Zero Trust SSH**: SSH only via WireGuard network
- ✅ **Key-based Auth**: No password authentication

## 📊 Health Check

```bash
./scripts/health-check.sh
```

```
╔══════════════════════════════════════════════════════════════╗
║           ZERO TRUST NETWORK - HEALTH CHECK                  ║
╚══════════════════════════════════════════════════════════════╝

━━━ NODE CONNECTIVITY ━━━
  ✓ hub-2 (10.10.0.2) - 5ms
  ✓ db-primary (10.10.0.10) - 240ms
  ✓ db-replica (10.10.0.11) - 238ms
```

## 📚 Documentation

- [Zero Trust Architecture](ZERO_TRUST_ARCHITECTURE.md) - Chi tiết kiến trúc
- [High Availability](HIGH_AVAILABILITY.md) - Hướng dẫn HA
- [WireGuard Mesh](WIREGUARD_MESH.md) - Cấu hình WireGuard

---

**Built with ❤️ for Zero Trust Security**

*100% tự chủ - Không phụ thuộc bên thứ 3*
