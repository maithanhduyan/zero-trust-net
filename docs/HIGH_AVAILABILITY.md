# High Availability Architecture

## 🎯 Mục Tiêu

Hệ thống vẫn hoạt động khi **bất kỳ node nào fail**.

## 📐 Kiến Trúc HA

```
                         ┌──────────────────────────────────────────────────────────────┐
                         │                      INTERNET                                │
                         └────────────────────────────┬─────────────────────────────────┘
                                                      │
                         ┌────────────────────────────┴─────────────────────────────────┐
                         │                    CONTROL PLANE CLUSTER                     │
                         │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
                         │  │   Hub 1     │◄──►│   Hub 2     │◄──►│   Hub 3     │       │
                         │  │  10.10.0.1  │    │  10.10.0.2  │    │  10.10.0.3  │       │
                         │  │  (Active)   │    │  (Standby)  │    │  (Standby)  │       │
                         │  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘       │
                         │         │                  │                  │              │
                         │         └──────────────────┼──────────────────┘              │
                         │                            │                                 │
                         │              Virtual IP: 10.10.0.100 (Keepalived)            │
                         └────────────────────────────┬─────────────────────────────────┘
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────────────┐
                    │                                 │                                 │
         ┌──────────┴──────────┐           ┌─────────┴─────────┐           ┌───────────┴──────────┐
         │   DATABASE CLUSTER  │           │   APP CLUSTER     │           │   MONITORING         │
         │                     │           │                   │           │                      │
         │  ┌───────┐ ┌───────┐│           │ ┌───────┐┌───────┐│           │ ┌───────┐            │
         │  │Primary│◄►Replica││           │ │ Odoo1 ││ Odoo2 ││           │ │Monitor│            │
         │  │ .10   │ │ .11   ││           │ │ .20   ││ .21   ││           │ │ .30   │            │
         │  └───────┘ └───────┘│           │ └───────┘└───────┘│           │ └───────┘            │
         │     ↑ Patroni ↓     │           │     HAProxy       │           │                      │
         │   Auto Failover     │           │   Load Balance    │           │                      │
         └─────────────────────┘           └───────────────────┘           └──────────────────────┘
```

## 🔄 Failover Scenarios

### Scenario 1: Hub Server Fail

```
BEFORE:                           AFTER:
Hub 1 (Active) ─── Workers        Hub 1 ❌
                                  Hub 2 (New Active) ─── Workers
                                  
Keepalived chuyển VIP sang Hub 2
Workers tự động kết nối lại
```

### Scenario 2: Database Primary Fail

```
BEFORE:                           AFTER:
Primary (10.10.0.10) ─── Apps     Primary ❌
Replica (10.10.0.11) ─ sync       Replica → New Primary (10.10.0.11)
                                  Apps tự động chuyển sang .11
                                  
Patroni tự động promote Replica
```

### Scenario 3: App Server Fail

```
BEFORE:                           AFTER:
Odoo 1 ─┬─ HAProxy               Odoo 1 ❌
Odoo 2 ─┘                        Odoo 2 ─── HAProxy
                                  
HAProxy health check và loại bỏ node hỏng
```

## 🛠️ Components

### 1. Multi-Hub WireGuard
- 3 Hub servers (có thể 2 minimum)
- Mỗi worker kết nối đến TẤT CẢ hubs
- Nếu hub1 fail → traffic qua hub2

### 2. Keepalived (Virtual IP)
- VIP: 10.10.0.100
- Chạy trên các Hub servers
- Auto failover < 3 seconds

### 3. Patroni (PostgreSQL HA)
- Auto failover PostgreSQL
- etcd/Consul cho consensus
- Automatic promotion replica → primary

### 4. HAProxy (Load Balancer)
- Phân tải traffic đến Odoo servers
- Health checks
- Automatic removal of failed nodes

## 📋 Deployment Order

1. Setup Multi-Hub WireGuard
2. Setup Keepalived trên Hubs
3. Setup PostgreSQL với Patroni
4. Setup Odoo cluster với HAProxy
5. Setup Monitoring (detect failures)

## 🔢 Minimum Nodes for HA

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Hub/Control Plane | 2 | 3 |
| Database | 2 | 3 |
| Application | 2 | 3+ |
| Monitoring | 1 | 2 |

**Total minimum: 7 nodes** cho full HA
**Current: 3 nodes** → Cần thêm nodes cho HA

## ⚡ Quick HA (Với 3 nodes hiện tại)

Với 3 nodes hiện có, có thể setup:

```
Hub (10.10.0.1) + Keepalived + HAProxy
     │
     ├── db-primary (10.10.0.10) + Patroni
     │
     └── db-replica (10.10.0.11) + Patroni + Odoo (backup)
```

- PostgreSQL: Primary-Replica với auto-failover
- Nếu Primary fail → Replica tự động lên Primary
- Hub fail → Cần manual intervention (chưa có HA cho Hub)
