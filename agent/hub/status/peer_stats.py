"""
Peer Statistics for Hub Agent

Detailed peer statistics:
- Handshake times
- Transfer rates
- Connection quality
- Historical data
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from collections import defaultdict

logger = logging.getLogger('hub-agent.peer_stats')


class PeerStats:
    """
    Collects and tracks peer statistics
    """

    def __init__(self, interface: str = "wg0"):
        """
        Initialize peer stats collector

        Args:
            interface: WireGuard interface name
        """
        self.interface = interface

        # Historical tracking
        self._previous_stats: dict[str, dict] = {}
        self._last_collection: Optional[datetime] = None

    async def get_all_stats(self) -> dict:
        """
        Get statistics for all peers

        Returns:
            Dict with peers list and aggregate stats
        """
        now = datetime.utcnow()
        peers = await self._collect_peer_stats()

        # Calculate rates if we have previous data
        if self._last_collection and self._previous_stats:
            elapsed = (now - self._last_collection).total_seconds()
            if elapsed > 0:
                for peer in peers:
                    key = peer["public_key"]
                    if key in self._previous_stats:
                        prev = self._previous_stats[key]
                        peer["rx_rate"] = (peer["transfer_rx"] - prev.get("transfer_rx", 0)) / elapsed
                        peer["tx_rate"] = (peer["transfer_tx"] - prev.get("transfer_tx", 0)) / elapsed

        # Update tracking
        self._previous_stats = {p["public_key"]: p.copy() for p in peers}
        self._last_collection = now

        # Aggregate stats
        total_rx = sum(p.get("transfer_rx", 0) for p in peers)
        total_tx = sum(p.get("transfer_tx", 0) for p in peers)
        connected_count = sum(1 for p in peers if p.get("is_connected"))

        return {
            "timestamp": now.isoformat(),
            "interface": self.interface,
            "peers": peers,
            "summary": {
                "total_peers": len(peers),
                "connected_peers": connected_count,
                "disconnected_peers": len(peers) - connected_count,
                "total_rx_bytes": total_rx,
                "total_tx_bytes": total_tx,
                "total_rx_human": self._human_bytes(total_rx),
                "total_tx_human": self._human_bytes(total_tx),
            }
        }

    async def get_peer_stats(self, public_key: str) -> Optional[dict]:
        """
        Get statistics for a specific peer

        Args:
            public_key: Peer's public key

        Returns:
            Peer stats dict or None if not found
        """
        peers = await self._collect_peer_stats()

        for peer in peers:
            if peer["public_key"] == public_key:
                return peer

        return None

    async def get_connected_peers(self) -> list[dict]:
        """Get list of currently connected peers"""
        peers = await self._collect_peer_stats()
        return [p for p in peers if p.get("is_connected")]

    async def get_disconnected_peers(self) -> list[dict]:
        """Get list of disconnected peers"""
        peers = await self._collect_peer_stats()
        return [p for p in peers if not p.get("is_connected")]

    async def _collect_peer_stats(self) -> list[dict]:
        """Collect raw peer statistics from WireGuard"""
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
            now = int(datetime.utcnow().timestamp())

            # Skip first line (interface info)
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 5:
                    latest_handshake = int(parts[4]) if parts[4] and parts[4] != "0" else 0
                    handshake_ago = now - latest_handshake if latest_handshake else None

                    # Connected if handshake within last 3 minutes (180 seconds)
                    is_connected = handshake_ago is not None and handshake_ago < 180

                    transfer_rx = int(parts[5]) if len(parts) > 5 else 0
                    transfer_tx = int(parts[6]) if len(parts) > 6 else 0

                    peers.append({
                        "public_key": parts[0],
                        "public_key_short": parts[0][:16] + "...",
                        "preshared_key": parts[1] != "(none)",
                        "endpoint": parts[2] if parts[2] != "(none)" else None,
                        "allowed_ips": parts[3],
                        "latest_handshake": latest_handshake or None,
                        "handshake_ago_seconds": handshake_ago,
                        "handshake_ago_human": self._human_time(handshake_ago) if handshake_ago else "never",
                        "transfer_rx": transfer_rx,
                        "transfer_tx": transfer_tx,
                        "transfer_rx_human": self._human_bytes(transfer_rx),
                        "transfer_tx_human": self._human_bytes(transfer_tx),
                        "persistent_keepalive": parts[7] if len(parts) > 7 and parts[7] != "off" else None,
                        "is_connected": is_connected,
                        "connection_status": "connected" if is_connected else ("stale" if latest_handshake else "never connected"),
                    })

            return peers

        except Exception as e:
            logger.error(f"Error collecting peer stats: {e}")
            return []

    @staticmethod
    def _human_bytes(num_bytes: int) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} PB"

    @staticmethod
    def _human_time(seconds: int) -> str:
        """Convert seconds to human readable format"""
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
