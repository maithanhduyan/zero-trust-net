"""
Interface Status for Hub Agent

Collects and reports WireGuard interface status:
- Interface up/down
- Listen port
- Public key
- Peer count
- Traffic summary
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger('hub-agent.status')


class InterfaceStatus:
    """
    Collects WireGuard interface status
    """

    def __init__(self, interface: str = "wg0"):
        """
        Initialize status collector

        Args:
            interface: WireGuard interface name
        """
        self.interface = interface

    async def get_full_status(self) -> dict:
        """
        Get comprehensive interface status

        Returns:
            Dict with interface info, peers, traffic, etc.
        """
        is_up = await self._is_interface_up()

        status = {
            "interface": self.interface,
            "is_up": is_up,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if is_up:
            # Get detailed info
            interface_info = await self._get_interface_info()
            status.update(interface_info)

            # Get peer summary
            peers = await self._get_peers_summary()
            status["peers"] = peers
            status["peer_count"] = len(peers)
            status["connected_peers"] = sum(1 for p in peers if p.get("is_connected"))

            # Traffic summary
            status["total_rx"] = sum(p.get("transfer_rx", 0) for p in peers)
            status["total_tx"] = sum(p.get("transfer_tx", 0) for p in peers)

        return status

    async def is_healthy(self) -> bool:
        """Check if interface is healthy (up and has at least one connected peer)"""
        status = await self.get_full_status()
        return status.get("is_up", False)

    async def _is_interface_up(self) -> bool:
        """Check if interface is up"""
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            return result.returncode == 0
        except Exception:
            return False

    async def _get_interface_info(self) -> dict:
        """Get interface information from wg show dump"""
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface, "dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()

            if result.returncode != 0:
                return {}

            lines = stdout.decode().strip().split('\n')
            if not lines:
                return {}

            # First line is interface info
            parts = lines[0].split('\t')
            if len(parts) >= 3:
                return {
                    "public_key": parts[1],
                    "listen_port": int(parts[2]) if parts[2] else None,
                }

            return {}

        except Exception as e:
            logger.error(f"Error getting interface info: {e}")
            return {}

    async def _get_peers_summary(self) -> list[dict]:
        """Get summary of all peers"""
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface, "dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()

            if result.returncode != 0:
                return []

            peers = []
            lines = stdout.decode().strip().split('\n')

            # Skip first line (interface info)
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 5:
                    # Calculate if peer is "connected" (handshake within last 3 minutes)
                    latest_handshake = int(parts[4]) if parts[4] and parts[4] != "0" else 0
                    now = int(datetime.utcnow().timestamp())
                    is_connected = (now - latest_handshake) < 180 if latest_handshake else False

                    peers.append({
                        "public_key": parts[0][:16] + "...",  # Truncate for safety
                        "public_key_full": parts[0],
                        "endpoint": parts[2] if parts[2] != "(none)" else None,
                        "allowed_ips": parts[3],
                        "latest_handshake": latest_handshake or None,
                        "latest_handshake_ago": now - latest_handshake if latest_handshake else None,
                        "transfer_rx": int(parts[5]) if len(parts) > 5 else 0,
                        "transfer_tx": int(parts[6]) if len(parts) > 6 else 0,
                        "is_connected": is_connected,
                    })

            return peers

        except Exception as e:
            logger.error(f"Error getting peers: {e}")
            return []
