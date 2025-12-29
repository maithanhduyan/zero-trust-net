"""
Zero Trust Hub Agent

Hub agent chạy native trên Hub server, nhận lệnh từ Control Plane (Docker)
qua WebSocket để quản lý WireGuard peers và firewall rules.

Khác với Node Agent:
- WireGuard server mode (không có Endpoint, có ListenPort)
- Quản lý TẤT CẢ peers (nodes + clients)
- Không đăng ký với Control Plane (xác thực bằng API key)
- Nhận commands: add_peer, remove_peer, sync_peers
- Enable IP forwarding và NAT masquerade
"""

__version__ = "1.0.0"
__all__ = ["HubAgent"]

from .hub_agent import HubAgent
