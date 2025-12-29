# Zero Trust Agent

Thư mục này chứa hai loại agent hoàn toàn tách biệt:

## Cấu trúc thư mục

```
agent/
├── hub/                    # Hub Agent (chạy trên Hub server)
│   ├── __init__.py
│   ├── pyproject.toml
│   ├── hub_agent.py        # Main daemon
│   ├── websocket_handler.py
│   ├── command_executor.py
│   ├── wireguard/          # WireGuard server mode
│   ├── firewall/           # NAT, forwarding
│   └── status/             # Interface monitoring
│
├── node/                   # Node Agent (chạy trên mỗi VPS)
│   ├── __init__.py
│   ├── pyproject.toml
│   ├── agent.py            # Main daemon
│   ├── client.py           # HTTP client
│   ├── websocket_client.py
│   ├── wireguard/          # WireGuard client mode
│   ├── firewall/           # ACL rules
│   └── collectors/         # Trust scoring metrics
│
└── README.md               # This file
```

## So sánh Hub Agent vs Node Agent

| Aspect | Hub Agent | Node Agent |
|--------|-----------|------------|
| **Vị trí** | Hub server (cùng host với Control Plane) | Mỗi VPS node |
| **Runtime** | Native (systemd) | Native (systemd) |
| **WireGuard mode** | **Server** (ListenPort, không có Endpoint) | **Client** (có Endpoint, kết nối TỚI hub) |
| **Peers** | Tất cả nodes + clients | Chỉ 1 peer (hub) |
| **Kết nối** | WebSocket từ localhost Control Plane | WebSocket/HTTP đến Control Plane |
| **Xác thực** | API key | Đăng ký + approve |
| **Commands nhận** | `add_peer`, `remove_peer`, `sync_peers` | `config_update`, `acl_update` |
| **IP Forwarding** | Có (sysctl) | Không |
| **NAT Masquerade** | Có | Không |
| **Trust Scoring** | Không (là hub) | Có (gửi metrics) |

## Hub Agent

Hub Agent chạy native trên Hub server, nhận lệnh từ Control Plane (Docker) qua WebSocket.

### Chức năng

- Kết nối WebSocket đến `ws://localhost:8000/api/v1/ws/hub`
- Nhận và thực thi commands từ Control Plane:
  - `add_peer`: Thêm WireGuard peer mới
  - `remove_peer`: Xóa peer
  - `sync_peers`: Đồng bộ danh sách peers
  - `get_status`: Lấy trạng thái interface
- Quản lý WireGuard interface (wg0) ở chế độ server
- Enable IP forwarding và NAT masquerade
- Báo cáo status định kỳ

### Cài đặt

```bash
cd agent/hub
pip install -e .

# Hoặc dùng uv
uv pip install -e .
```

### Chạy

```bash
# Với environment variables
export HUB_API_KEY="your-secret-key"
export CONTROL_PLANE_URL="ws://localhost:8000/api/v1/ws/hub"
hub-agent

# Hoặc với arguments
hub-agent --api-key "your-secret-key" --interface wg0
```

### Systemd Service

```ini
[Unit]
Description=Zero Trust Hub Agent
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=root
Environment=HUB_API_KEY=your-secret-key
ExecStart=/usr/local/bin/hub-agent
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Node Agent

Node Agent chạy trên mỗi VPS, kết nối đến Control Plane để nhận cấu hình.

### Chức năng

- Đăng ký với Control Plane qua HTTP API
- Kết nối WebSocket để nhận updates real-time
- Apply WireGuard configuration (client mode)
- Apply firewall rules (iptables ZT_ACL chain)
- Gửi heartbeat với metrics cho trust scoring:
  - CPU, Memory, Disk usage
  - Security events (SSH failures, firewall drops)
  - Network statistics
  - Agent integrity hash

### Cài đặt

```bash
cd agent/node
pip install -e .

# Với full dependencies (psutil, distro)
pip install -e ".[full]"
```

### Chạy

```bash
node-agent \
  --hostname my-vps \
  --role app \
  --control-plane https://hub.example.com \
  --sync-interval 60
```

### Systemd Service

```ini
[Unit]
Description=Zero Trust Node Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/node-agent --hostname %H --role app --control-plane https://hub.example.com
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Kiến trúc

```
┌────────────────────────────────────────────────────────────────┐
│                        HUB SERVER                               │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Docker Containers                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │control-plane│  │   web-ui    │  │     traefik     │  │   │
│  │  │   :8000     │  │   :3000     │  │   :80/:443      │  │   │
│  │  └──────┬──────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────┼───────────────────────────────────────────────┘   │
│            │ WebSocket                                          │
│            ▼                                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Hub Agent (Native)                      │   │
│  │  ┌─────────────────┐  ┌─────────────────────────────┐   │   │
│  │  │ WebSocket Handler│  │     WireGuard Manager       │   │   │
│  │  │ - add_peer      │─▶│     - wg set peer           │   │   │
│  │  │ - remove_peer   │  │     - wg-quick save         │   │   │
│  │  └─────────────────┘  └──────────────┬──────────────┘   │   │
│  └──────────────────────────────────────┼──────────────────┘   │
│                                         │                       │
│  ┌──────────────────────────────────────▼──────────────────┐   │
│  │              WireGuard wg0 (Server Mode)                 │   │
│  │              10.10.0.1/24 - :51820/udp                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ WireGuard Tunnel
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│                        NODE SERVER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Node Agent (Native)                     │   │
│  │  ┌─────────────────┐  ┌─────────────────────────────┐   │   │
│  │  │ WebSocket Client │  │     WireGuard Manager       │   │   │
│  │  │ - config_update │─▶│     - update peers          │   │   │
│  │  │ - acl_update    │  │     - apply config          │   │   │
│  │  └─────────────────┘  └──────────────┬──────────────┘   │   │
│  │                                      │                   │   │
│  │  ┌─────────────────┐  ┌──────────────▼──────────────┐   │   │
│  │  │   Collectors    │  │     Firewall (iptables)     │   │   │
│  │  │ - host_info     │  │     - ZT_ACL chain          │   │   │
│  │  │ - security      │  │     - ACL rules             │   │   │
│  │  │ - network       │  └─────────────────────────────┘   │   │
│  │  └─────────────────┘                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              WireGuard wg0 (Client Mode)                 │   │
│  │              10.10.0.X/24 - Endpoint: hub:51820          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Development

### Testing Hub Agent

```bash
cd agent/hub
pip install -e ".[dev]"
pytest
```

### Testing Node Agent

```bash
cd agent/node
pip install -e ".[dev]"
pytest
```

## Lưu ý quan trọng

1. **Tách biệt hoàn toàn**: Hub và Node agent KHÔNG chia sẻ code. Điều này đảm bảo có thể upgrade độc lập mà không ảnh hưởng lẫn nhau.

2. **Dependencies riêng biệt**: Mỗi agent có pyproject.toml riêng với dependencies phù hợp.

3. **WireGuard modes khác nhau**:
   - Hub: Server mode (ListenPort, không Endpoint)
   - Node: Client mode (có Endpoint trỏ đến Hub)

4. **Security**:
   - Hub Agent xác thực bằng API key
   - Node Agent đăng ký và cần được approve bởi admin
