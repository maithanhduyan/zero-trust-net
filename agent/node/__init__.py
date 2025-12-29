"""
Zero Trust Node Agent

Node agent chạy trên mỗi VPS, kết nối đến Control Plane (Hub)
để nhận cấu hình WireGuard và firewall rules.

Khác với Hub Agent:
- WireGuard client mode (có Endpoint, kết nối TỚI hub)
- Chỉ có 1 peer (hub)
- Đăng ký với Control Plane qua HTTP API
- Gửi heartbeat và metrics cho trust scoring
- Nhận commands: config_update, acl_update
"""

__version__ = "1.0.0"
__all__ = ["ZeroTrustAgent"]

from .agent import ZeroTrustAgent
