"""
Hub WireGuard Module

WireGuard management for Hub server mode:
- Server mode (ListenPort, no Endpoint)
- Manage all node/client peers
- Interface lifecycle
"""

from .manager import WireGuardManager
from .peer_manager import PeerManager

__all__ = ["WireGuardManager", "PeerManager"]
