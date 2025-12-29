"""
Command Executor for Hub Agent

Routes commands from Control Plane to appropriate handlers:
- add_peer: Add new WireGuard peer
- remove_peer: Remove WireGuard peer
- update_peer: Update peer configuration
- sync_peers: Synchronize all peers
- get_status: Get interface status
- restart_interface: Restart WireGuard interface
"""

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from wireguard.manager import WireGuardManager
    from wireguard.peer_manager import PeerManager
    from firewall.iptables import HubFirewall
    from status.interface_status import InterfaceStatus
    from status.peer_stats import PeerStats

logger = logging.getLogger('hub-agent.executor')


class CommandExecutor:
    """
    Executes commands received from Control Plane
    """

    def __init__(
        self,
        wg_manager: "WireGuardManager",
        peer_manager: "PeerManager",
        firewall: "HubFirewall",
        interface_status: "InterfaceStatus",
        peer_stats: "PeerStats",
    ):
        """
        Initialize command executor with all managers
        """
        self.wg_manager = wg_manager
        self.peer_manager = peer_manager
        self.firewall = firewall
        self.interface_status = interface_status
        self.peer_stats = peer_stats

        # Command handlers mapping
        self._handlers = {
            "add_peer": self._handle_add_peer,
            "remove_peer": self._handle_remove_peer,
            "update_peer": self._handle_update_peer,
            "sync_peers": self._handle_sync_peers,
            "get_peers": self._handle_get_peers,
            "get_status": self._handle_get_status,
            "get_peer_stats": self._handle_get_peer_stats,
            "restart_interface": self._handle_restart_interface,
            "ping": self._handle_ping,
        }

    async def execute(self, command_type: str, payload: dict) -> dict[str, Any]:
        """
        Execute a command

        Args:
            command_type: Type of command
            payload: Command payload

        Returns:
            Result dict with success, data, error keys
        """
        handler = self._handlers.get(command_type)

        if not handler:
            logger.warning(f"Unknown command type: {command_type}")
            return {
                "success": False,
                "error": f"Unknown command type: {command_type}",
            }

        logger.info(f"Executing command: {command_type}")

        try:
            result = await handler(payload)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Command failed: {command_type} - {e}")
            return {"success": False, "error": str(e)}

    async def _handle_add_peer(self, payload: dict) -> dict:
        """
        Add a new WireGuard peer

        Expected payload:
        {
            "public_key": "xxx",
            "allowed_ips": "10.10.0.5/32",
            "preshared_key": "optional",
            "persistent_keepalive": 25
        }
        """
        public_key = payload.get("public_key")
        allowed_ips = payload.get("allowed_ips")
        preshared_key = payload.get("preshared_key")
        keepalive = payload.get("persistent_keepalive", 0)

        if not public_key or not allowed_ips:
            raise ValueError("public_key and allowed_ips required")

        await self.peer_manager.add_peer(
            public_key=public_key,
            allowed_ips=allowed_ips,
            preshared_key=preshared_key,
            persistent_keepalive=keepalive,
        )

        logger.info(f"Added peer: {public_key[:16]}... -> {allowed_ips}")

        return {
            "public_key": public_key,
            "allowed_ips": allowed_ips,
            "status": "added",
        }

    async def _handle_remove_peer(self, payload: dict) -> dict:
        """
        Remove a WireGuard peer

        Expected payload:
        {
            "public_key": "xxx"
        }
        """
        public_key = payload.get("public_key")

        if not public_key:
            raise ValueError("public_key required")

        await self.peer_manager.remove_peer(public_key)

        logger.info(f"Removed peer: {public_key[:16]}...")

        return {
            "public_key": public_key,
            "status": "removed",
        }

    async def _handle_update_peer(self, payload: dict) -> dict:
        """
        Update an existing peer's configuration

        Expected payload:
        {
            "public_key": "xxx",
            "allowed_ips": "10.10.0.5/32,10.10.0.6/32",
            "preshared_key": "optional"
        }
        """
        public_key = payload.get("public_key")
        allowed_ips = payload.get("allowed_ips")

        if not public_key:
            raise ValueError("public_key required")

        await self.peer_manager.update_peer(
            public_key=public_key,
            allowed_ips=allowed_ips,
        )

        logger.info(f"Updated peer: {public_key[:16]}...")

        return {
            "public_key": public_key,
            "status": "updated",
        }

    async def _handle_sync_peers(self, payload: dict) -> dict:
        """
        Synchronize all peers with the provided list
        Removes peers not in list, adds missing peers

        Expected payload:
        {
            "peers": [
                {"public_key": "xxx", "allowed_ips": "10.10.0.5/32"},
                ...
            ]
        }
        """
        peers = payload.get("peers", [])

        result = await self.peer_manager.sync_peers(peers)

        logger.info(f"Synced peers: added={result['added']}, removed={result['removed']}")

        return result

    async def _handle_get_status(self, payload: dict) -> dict:
        """Get current interface status"""
        return await self.interface_status.get_full_status()

    async def _handle_get_peers(self, payload: dict) -> dict:
        """Get list of all current WireGuard peers"""
        peers = await self.peer_stats.get_all_stats()
        return {"peers": peers.get("peers", [])}

    async def _handle_get_peer_stats(self, payload: dict) -> dict:
        """Get peer statistics (handshakes, transfer)"""
        return await self.peer_stats.get_all_stats()

    async def _handle_restart_interface(self, payload: dict) -> dict:
        """Restart WireGuard interface"""
        await self.wg_manager.restart_interface()

        logger.info("Interface restarted")

        return {"status": "restarted"}

    async def _handle_ping(self, payload: dict) -> dict:
        """Respond to ping"""
        return {"pong": True}

    async def get_interface_status(self) -> dict:
        """Get current interface status (convenience method)"""
        return await self.interface_status.get_full_status()
