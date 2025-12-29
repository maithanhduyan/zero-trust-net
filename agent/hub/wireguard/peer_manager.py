"""
Peer Manager for Hub Agent

High-level peer management:
- Add/remove/update peers
- Sync peers with control-plane list
- Track peer states
"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import WireGuardManager

logger = logging.getLogger('hub-agent.peer_manager')


class PeerManager:
    """
    High-level peer management for Hub
    """

    def __init__(self, wg_manager: "WireGuardManager"):
        """
        Initialize peer manager

        Args:
            wg_manager: WireGuardManager instance
        """
        self.wg_manager = wg_manager

        # Local cache of peers (updated on sync)
        self._peers_cache: dict[str, dict] = {}

    async def add_peer(
        self,
        public_key: str,
        allowed_ips: str,
        preshared_key: Optional[str] = None,
        persistent_keepalive: int = 0,
    ) -> bool:
        """
        Add a new peer

        Args:
            public_key: Peer's public key
            allowed_ips: Allowed IPs
            preshared_key: Optional preshared key
            persistent_keepalive: Keepalive interval

        Returns:
            True if successful
        """
        # Check if peer already exists
        if public_key in self._peers_cache:
            logger.warning(f"Peer already exists: {public_key[:16]}...")
            # Update instead
            return await self.update_peer(public_key, allowed_ips)

        success = await self.wg_manager.add_peer(
            public_key=public_key,
            allowed_ips=allowed_ips,
            preshared_key=preshared_key,
            persistent_keepalive=persistent_keepalive,
        )

        if success:
            self._peers_cache[public_key] = {
                "public_key": public_key,
                "allowed_ips": allowed_ips,
                "preshared_key": preshared_key is not None,
                "persistent_keepalive": persistent_keepalive,
            }

        return success

    async def remove_peer(self, public_key: str) -> bool:
        """
        Remove a peer

        Args:
            public_key: Peer's public key

        Returns:
            True if successful
        """
        success = await self.wg_manager.remove_peer(public_key)

        if success:
            self._peers_cache.pop(public_key, None)

        return success

    async def update_peer(
        self,
        public_key: str,
        allowed_ips: Optional[str] = None,
    ) -> bool:
        """
        Update an existing peer

        Args:
            public_key: Peer's public key
            allowed_ips: New allowed IPs (if changing)

        Returns:
            True if successful
        """
        if allowed_ips:
            # WireGuard doesn't have an "update" command
            # Just re-add with new allowed-ips
            success = await self.wg_manager.add_peer(
                public_key=public_key,
                allowed_ips=allowed_ips,
            )

            if success and public_key in self._peers_cache:
                self._peers_cache[public_key]["allowed_ips"] = allowed_ips

            return success

        return True  # Nothing to update

    async def sync_peers(self, desired_peers: list[dict]) -> dict:
        """
        Synchronize peers with desired list

        Removes peers not in list, adds missing peers.

        Args:
            desired_peers: List of dicts with public_key, allowed_ips, etc.

        Returns:
            Dict with added, removed, unchanged counts
        """
        # Get current peers
        current_peers = await self.wg_manager.get_peers()
        current_keys = {p["public_key"]: p for p in current_peers}

        # Build desired set
        desired_keys = {p["public_key"]: p for p in desired_peers}

        added = 0
        removed = 0
        updated = 0
        unchanged = 0
        errors = []

        # Remove peers not in desired list
        for key in current_keys:
            if key not in desired_keys:
                try:
                    await self.remove_peer(key)
                    removed += 1
                    logger.info(f"Removed stale peer: {key[:16]}...")
                except Exception as e:
                    errors.append(f"remove {key[:16]}: {e}")

        # Add or update peers
        for key, peer in desired_keys.items():
            if key not in current_keys:
                # Add new peer
                try:
                    await self.add_peer(
                        public_key=peer["public_key"],
                        allowed_ips=peer.get("allowed_ips", ""),
                        preshared_key=peer.get("preshared_key"),
                        persistent_keepalive=peer.get("persistent_keepalive", 0),
                    )
                    added += 1
                except Exception as e:
                    errors.append(f"add {key[:16]}: {e}")
            else:
                # Check if update needed
                current = current_keys[key]
                if current.get("allowed_ips") != peer.get("allowed_ips"):
                    try:
                        await self.update_peer(
                            public_key=key,
                            allowed_ips=peer.get("allowed_ips"),
                        )
                        updated += 1
                    except Exception as e:
                        errors.append(f"update {key[:16]}: {e}")
                else:
                    unchanged += 1

        # Update cache
        self._peers_cache = desired_keys.copy()

        result = {
            "added": added,
            "removed": removed,
            "updated": updated,
            "unchanged": unchanged,
            "total": len(desired_keys),
        }

        if errors:
            result["errors"] = errors

        return result

    async def get_peer_count(self) -> int:
        """Get number of configured peers"""
        peers = await self.wg_manager.get_peers()
        return len(peers)

    async def peer_exists(self, public_key: str) -> bool:
        """Check if a peer exists"""
        peers = await self.wg_manager.get_peers()
        return any(p["public_key"] == public_key for p in peers)

    async def refresh_cache(self):
        """Refresh local peer cache from WireGuard"""
        peers = await self.wg_manager.get_peers()
        self._peers_cache = {p["public_key"]: p for p in peers}
        logger.debug(f"Refreshed cache: {len(self._peers_cache)} peers")
