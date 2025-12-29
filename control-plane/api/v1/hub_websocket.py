# control-plane/api/v1/hub_websocket.py
"""
WebSocket API for Hub Agent Communication

Hub Agent runs on the same server as Control Plane (or separate Hub server).
It receives commands to manage WireGuard peers and firewall rules.

Commands from Control Plane to Hub Agent:
- add_peer: Add a new WireGuard peer
- remove_peer: Remove a WireGuard peer
- update_peer: Update peer configuration
- sync_peers: Full sync of all peers
- get_status: Request Hub status
- restart_interface: Restart WireGuard interface
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session

from database.session import get_db_session
from database.models import Node, NodeStatus
from core.events import event_bus, Event, EventPriority
from core.domain_events import EventTypes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Hub WebSocket"])


@dataclass
class HubConnection:
    """Track Hub Agent connection state"""
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    hub_status: Dict[str, Any] = field(default_factory=dict)


class HubWebSocketManager:
    """
    Manages WebSocket connection for Hub Agent

    Only one Hub Agent should be connected at a time.
    Provides command/response communication pattern.
    """

    def __init__(self):
        self._connection: Optional[HubConnection] = None
        self._lock = asyncio.Lock()
        self._pending_commands: Dict[str, asyncio.Future] = {}
        self._command_counter = 0

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def connection_info(self) -> Optional[dict]:
        if not self._connection:
            return None
        return {
            "connected_at": self._connection.connected_at.isoformat(),
            "last_ping": self._connection.last_ping.isoformat(),
            "hub_status": self._connection.hub_status
        }

    async def connect(self, websocket: WebSocket) -> bool:
        """
        Register Hub Agent connection

        Returns True if connection accepted
        """
        await websocket.accept()

        async with self._lock:
            # Close existing connection (hub agent reconnecting)
            if self._connection:
                try:
                    await self._connection.websocket.close(
                        code=1000,
                        reason="Replaced by new connection"
                    )
                except Exception:
                    pass
                logger.info("Replaced existing Hub Agent connection")

            self._connection = HubConnection(websocket=websocket)

        logger.info("Hub Agent connected")
        return True

    async def disconnect(self) -> None:
        """Remove Hub Agent connection"""
        async with self._lock:
            if self._connection:
                self._connection = None
                logger.info("Hub Agent disconnected")

                # Cancel all pending commands
                for cmd_id, future in self._pending_commands.items():
                    if not future.done():
                        future.set_exception(
                            ConnectionError("Hub Agent disconnected")
                        )
                self._pending_commands.clear()

    async def send_command(
        self,
        command: str,
        payload: dict,
        timeout: float = 30.0
    ) -> dict:
        """
        Send command to Hub Agent and wait for response

        Args:
            command: Command type (add_peer, remove_peer, etc.)
            payload: Command payload
            timeout: Timeout in seconds

        Returns:
            Response from Hub Agent

        Raises:
            ConnectionError: If Hub Agent not connected
            TimeoutError: If command times out
        """
        if not self._connection:
            raise ConnectionError("Hub Agent not connected")

        # Generate unique command ID
        async with self._lock:
            self._command_counter += 1
            cmd_id = f"cmd_{self._command_counter}"

        message = {
            "id": cmd_id,
            "type": "command",
            "command": command,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Create future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_commands[cmd_id] = future

        try:
            # Send command
            await self._connection.websocket.send_json(message)
            logger.debug(f"Sent command {cmd_id}: {command}")

            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            logger.error(f"Command {cmd_id} timed out")
            raise TimeoutError(f"Command {command} timed out after {timeout}s")
        finally:
            self._pending_commands.pop(cmd_id, None)

    def handle_response(self, cmd_id: str, response: dict) -> bool:
        """
        Handle response from Hub Agent

        Returns True if response was matched to a pending command
        """
        if cmd_id in self._pending_commands:
            future = self._pending_commands[cmd_id]
            if not future.done():
                future.set_result(response)
                return True
        return False

    def update_status(self, status: dict) -> None:
        """Update Hub Agent status"""
        if self._connection:
            self._connection.hub_status = status
            self._connection.last_ping = datetime.utcnow()

    # =========================================================================
    # High-level Commands
    # =========================================================================

    async def add_peer(
        self,
        public_key: str,
        allowed_ips: str,
        endpoint: Optional[str] = None,
        persistent_keepalive: int = 25
    ) -> dict:
        """Add a WireGuard peer"""
        return await self.send_command("add_peer", {
            "public_key": public_key,
            "allowed_ips": allowed_ips,
            "endpoint": endpoint,
            "persistent_keepalive": persistent_keepalive
        })

    async def remove_peer(self, public_key: str) -> dict:
        """Remove a WireGuard peer"""
        return await self.send_command("remove_peer", {
            "public_key": public_key
        })

    async def update_peer(
        self,
        public_key: str,
        allowed_ips: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> dict:
        """Update a WireGuard peer"""
        payload = {"public_key": public_key}
        if allowed_ips:
            payload["allowed_ips"] = allowed_ips
        if endpoint:
            payload["endpoint"] = endpoint
        return await self.send_command("update_peer", payload)

    async def sync_peers(self, peers: list) -> dict:
        """
        Full sync of all peers

        Args:
            peers: List of peer configs [{public_key, allowed_ips, endpoint}, ...]
        """
        return await self.send_command("sync_peers", {"peers": peers})

    async def get_hub_status(self) -> dict:
        """Request Hub status"""
        return await self.send_command("get_status", {})

    async def get_peer_stats(self) -> dict:
        """Request peer statistics"""
        return await self.send_command("get_peer_stats", {})

    async def restart_interface(self) -> dict:
        """Restart WireGuard interface"""
        return await self.send_command("restart_interface", {})


# Singleton instance
hub_ws_manager = HubWebSocketManager()


# =============================================================================
# Event Handlers - React to system events by commanding Hub Agent
# =============================================================================

async def on_node_registered(event: Event) -> None:
    """When a new node is registered and approved, add as WireGuard peer"""
    if not hub_ws_manager.is_connected:
        logger.warning("Hub Agent not connected, cannot add peer")
        return

    payload = event.payload
    if payload.get("status") != NodeStatus.ACTIVE.value:
        return  # Only add active nodes

    try:
        overlay_ip = payload.get('overlay_ip', '')
        # Strip any existing CIDR before adding /32
        ip_address = overlay_ip.split('/')[0] if overlay_ip else ''
        result = await hub_ws_manager.add_peer(
            public_key=payload.get("public_key"),
            allowed_ips=f"{ip_address}/32"
        )
        logger.info(f"Added peer for node {payload.get('hostname')}: {result}")
    except Exception as e:
        logger.error(f"Failed to add peer: {e}")


async def on_node_revoked(event: Event) -> None:
    """When a node is revoked, remove from WireGuard"""
    if not hub_ws_manager.is_connected:
        logger.warning("Hub Agent not connected, cannot remove peer")
        return

    try:
        result = await hub_ws_manager.remove_peer(
            public_key=event.payload.get("public_key")
        )
        logger.info(f"Removed peer for node {event.payload.get('hostname')}: {result}")
    except Exception as e:
        logger.error(f"Failed to remove peer: {e}")


def register_hub_event_handlers():
    """Register event handlers for Hub Agent commands"""
    event_bus.subscribe(
        EventTypes.NODE_REGISTERED,
        on_node_registered,
        EventPriority.HIGH
    )
    event_bus.subscribe(
        EventTypes.NODE_REVOKED,
        on_node_revoked,
        EventPriority.HIGH
    )
    logger.info("Hub WebSocket event handlers registered")


# =============================================================================
# WebSocket Endpoint
# =============================================================================

@router.websocket("/ws/hub")
async def hub_websocket(
    websocket: WebSocket,
    api_key: str = Query(..., description="Hub Agent API key")
):
    """
    WebSocket endpoint for Hub Agent communication

    Authentication: Hub Agent must provide valid API key.
    The API key should match HUB_AGENT_API_KEY environment variable.

    Messages from Control Plane to Hub:
    - {"id": "...", "type": "command", "command": "add_peer", "payload": {...}}
    - {"id": "...", "type": "command", "command": "remove_peer", "payload": {...}}
    - {"id": "...", "type": "command", "command": "sync_peers", "payload": {...}}
    - {"id": "...", "type": "command", "command": "get_status", "payload": {}}

    Messages from Hub to Control Plane:
    - {"id": "...", "type": "response", "success": true, "data": {...}}
    - {"type": "status", "data": {...}} - Periodic status update
    - {"type": "ping"} - Keepalive
    """
    # Authenticate Hub Agent
    expected_key = os.environ.get("HUB_AGENT_API_KEY", "")
    if not expected_key or api_key != expected_key:
        await websocket.close(code=4001, reason="Invalid API key")
        logger.warning("Hub Agent connection rejected: invalid API key")
        return

    # Accept connection
    await hub_ws_manager.connect(websocket)

    try:
        # Send initial sync request
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to Control Plane",
            "timestamp": datetime.utcnow().isoformat()
        })

        while True:
            # Receive message from Hub Agent
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type in ("response", "command_result"):
                    # Response to a command
                    # Support both "id" and "command_id" field names
                    cmd_id = message.get("id") or message.get("command_id")
                    if cmd_id:
                        hub_ws_manager.handle_response(cmd_id, message)

                elif msg_type == "status":
                    # Periodic status update
                    hub_ws_manager.update_status(message.get("data", {}))
                    logger.debug("Received Hub status update")

                elif msg_type == "ping":
                    # Keepalive ping
                    if hub_ws_manager._connection:
                        hub_ws_manager._connection.last_ping = datetime.utcnow()
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "event":
                    # Event from Hub Agent (e.g., peer connected/disconnected)
                    event_name = message.get("event")
                    logger.info(f"Hub Agent event: {event_name}")
                    # Could publish to event_bus if needed

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from Hub Agent: {data[:100]}")

    except WebSocketDisconnect:
        logger.info("Hub Agent disconnected normally")
    except Exception as e:
        logger.error(f"Hub WebSocket error: {e}")
    finally:
        await hub_ws_manager.disconnect()


# =============================================================================
# REST Endpoints for Hub Management
# =============================================================================

@router.get("/hub/status")
async def get_hub_status():
    """Get Hub Agent connection status"""
    if not hub_ws_manager.is_connected:
        return {
            "connected": False,
            "message": "Hub Agent not connected"
        }

    return {
        "connected": True,
        "info": hub_ws_manager.connection_info
    }


@router.post("/hub/sync")
async def trigger_sync():
    """Trigger full peer sync on Hub Agent"""
    if not hub_ws_manager.is_connected:
        return {"success": False, "error": "Hub Agent not connected"}

    # Get all active nodes from database
    db = get_db_session()
    try:
        nodes = db.query(Node).filter(
            Node.status == NodeStatus.ACTIVE.value
        ).all()

        peers = [
            {
                "public_key": node.public_key,
                # Strip any existing CIDR before adding /32
                "allowed_ips": f"{node.overlay_ip.split('/')[0]}/32",
                "endpoint": None  # Nodes don't need endpoint, they connect to Hub
            }
            for node in nodes
        ]
    finally:
        db.close()

    try:
        result = await hub_ws_manager.sync_peers(peers)
        return {"success": True, "result": result, "peer_count": len(peers)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/hub/peers")
async def get_hub_peers():
    """Get peer statistics from Hub Agent"""
    if not hub_ws_manager.is_connected:
        return {"success": False, "error": "Hub Agent not connected"}

    try:
        result = await hub_ws_manager.get_peer_stats()
        return {"success": True, "data": result.get("data", {})}
    except Exception as e:
        return {"success": False, "error": str(e)}
