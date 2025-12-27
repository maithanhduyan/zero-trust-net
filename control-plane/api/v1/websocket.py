# control-plane/api/v1/websocket.py
"""
WebSocket API for Real-time Agent Communication

Replaces 60-second polling with push notifications.
Agents maintain persistent WebSocket connections to receive:
- Config updates
- Policy changes
- Trust score changes
- Admin commands
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Set
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from sqlalchemy.orm import Session

from database.session import get_db_session
from database.models import Node, NodeStatus
from core.events import event_bus, Event, EventPriority
from core.domain_events import EventTypes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@dataclass
class ConnectedAgent:
    """Track connected agent state"""
    websocket: WebSocket
    hostname: str
    node_id: int
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    config_version: int = 0


class WebSocketManager:
    """
    Manages WebSocket connections for all agents

    Provides:
    - Connection tracking by hostname
    - Broadcast to all/specific agents
    - Automatic ping/pong for keepalive
    - Reconnection handling
    """

    def __init__(self):
        self._connections: Dict[str, ConnectedAgent] = {}
        self._lock = asyncio.Lock()
        self._broadcast_queue: asyncio.Queue = asyncio.Queue()

    @property
    def connected_count(self) -> int:
        return len(self._connections)

    @property
    def connected_hostnames(self) -> Set[str]:
        return set(self._connections.keys())

    async def connect(self, websocket: WebSocket, hostname: str, node_id: int) -> bool:
        """
        Register a new agent connection

        Returns True if connection accepted, False if rejected
        """
        await websocket.accept()

        async with self._lock:
            # Close existing connection for same hostname (reconnection)
            if hostname in self._connections:
                old = self._connections[hostname]
                try:
                    await old.websocket.close(code=1000, reason="Replaced by new connection")
                except Exception:
                    pass
                logger.info(f"Replaced existing connection for {hostname}")

            self._connections[hostname] = ConnectedAgent(
                websocket=websocket,
                hostname=hostname,
                node_id=node_id
            )

        logger.info(f"Agent connected: {hostname} (total: {self.connected_count})")
        return True

    async def disconnect(self, hostname: str) -> None:
        """Remove an agent connection"""
        async with self._lock:
            if hostname in self._connections:
                del self._connections[hostname]
                logger.info(f"Agent disconnected: {hostname} (total: {self.connected_count})")

    async def send_to_agent(self, hostname: str, message: dict) -> bool:
        """Send message to a specific agent"""
        if hostname not in self._connections:
            return False

        agent = self._connections[hostname]
        try:
            await agent.websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {hostname}: {e}")
            await self.disconnect(hostname)
            return False

    async def broadcast(self, message: dict, exclude: Optional[Set[str]] = None) -> int:
        """
        Broadcast message to all connected agents

        Returns number of agents that received the message
        """
        exclude = exclude or set()
        sent_count = 0

        # Create snapshot of connections to avoid modification during iteration
        async with self._lock:
            targets = [
                (hostname, agent)
                for hostname, agent in self._connections.items()
                if hostname not in exclude
            ]

        for hostname, agent in targets:
            try:
                await agent.websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Broadcast failed for {hostname}: {e}")
                await self.disconnect(hostname)

        return sent_count

    async def notify_config_update(self, affected_hostnames: Optional[Set[str]] = None) -> int:
        """
        Notify agents that their config has been updated

        If affected_hostnames is None, notify all agents
        """
        message = {
            "type": "config_updated",
            "timestamp": datetime.utcnow().isoformat()
        }

        if affected_hostnames is None:
            return await self.broadcast(message)
        else:
            sent_count = 0
            for hostname in affected_hostnames:
                if await self.send_to_agent(hostname, message):
                    sent_count += 1
            return sent_count

    def get_agent_info(self, hostname: str) -> Optional[dict]:
        """Get info about a connected agent"""
        if hostname not in self._connections:
            return None

        agent = self._connections[hostname]
        return {
            "hostname": agent.hostname,
            "node_id": agent.node_id,
            "connected_at": agent.connected_at.isoformat(),
            "last_ping": agent.last_ping.isoformat(),
            "config_version": agent.config_version
        }

    def get_all_agents_info(self) -> list:
        """Get info about all connected agents"""
        return [self.get_agent_info(h) for h in self._connections.keys()]


# Singleton instance
ws_manager = WebSocketManager()


# =============================================================================
# Event Handlers for WebSocket Push
# =============================================================================

async def on_config_changed_ws(event: Event) -> None:
    """Push config update notification to agents via WebSocket"""
    payload = event.payload

    # Determine affected agents
    affected = payload.get("affected_nodes")
    if affected:
        affected_set = set(affected)
    else:
        affected_set = None  # Broadcast to all

    sent = await ws_manager.notify_config_update(affected_set)
    logger.info(f"Pushed config update to {sent} agents")


async def on_node_status_changed_ws(event: Event) -> None:
    """Notify specific node about their status change"""
    hostname = event.payload.get("hostname")
    if hostname:
        await ws_manager.send_to_agent(hostname, {
            "type": "status_changed",
            "new_status": event.payload.get("new_status"),
            "timestamp": datetime.utcnow().isoformat()
        })


def register_websocket_handlers():
    """Register WebSocket-specific event handlers"""
    # These handlers push notifications via WebSocket
    event_bus.subscribe(
        EventTypes.POLICY_UPDATED,
        on_config_changed_ws,
        EventPriority.NORMAL
    )
    event_bus.subscribe(
        EventTypes.NODE_REGISTERED,
        on_config_changed_ws,
        EventPriority.LOW
    )
    event_bus.subscribe(
        EventTypes.NODE_REVOKED,
        on_config_changed_ws,
        EventPriority.LOW
    )
    event_bus.subscribe(
        EventTypes.NODE_SUSPENDED,
        on_node_status_changed_ws,
        EventPriority.NORMAL
    )
    logger.info("WebSocket event handlers registered")


# =============================================================================
# WebSocket Endpoints
# =============================================================================

@router.websocket("/ws/agent/{hostname}")
async def agent_websocket(
    websocket: WebSocket,
    hostname: str,
    public_key: str = Query(..., description="Agent's WireGuard public key")
):
    """
    WebSocket endpoint for agent real-time communication

    Authentication: Agent must provide their WireGuard public key
    which is verified against the database.

    Messages from server:
    - {"type": "config_updated"} - Agent should fetch new config
    - {"type": "status_changed", "new_status": "..."} - Agent status changed
    - {"type": "pong"} - Response to ping

    Messages from agent:
    - {"type": "ping"} - Keepalive ping
    - {"type": "heartbeat", "metrics": {...}} - Agent metrics
    """
    # Authenticate agent by public key
    db = get_db_session()
    try:
        node = db.query(Node).filter(
            Node.hostname == hostname,
            Node.public_key == public_key,
            Node.status == NodeStatus.ACTIVE.value
        ).first()

        if not node:
            await websocket.close(code=4001, reason="Authentication failed")
            return

        node_id = node.id
    finally:
        db.close()

    # Accept connection
    await ws_manager.connect(websocket, hostname, node_id)

    try:
        while True:
            # Receive message from agent
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    # Update last ping time
                    if hostname in ws_manager._connections:
                        ws_manager._connections[hostname].last_ping = datetime.utcnow()
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "heartbeat":
                    # Update node last_seen and process metrics
                    db = get_db_session()
                    try:
                        node = db.query(Node).filter(Node.id == node_id).first()
                        if node:
                            node.last_seen = datetime.utcnow()
                            db.commit()
                    finally:
                        db.close()

                    # Acknowledge heartbeat
                    await websocket.send_json({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.utcnow().isoformat()
                    })

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from {hostname}: {data[:100]}")

    except WebSocketDisconnect:
        logger.info(f"Agent {hostname} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {hostname}: {e}")
    finally:
        await ws_manager.disconnect(hostname)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket connection status for all agents"""
    return {
        "connected_count": ws_manager.connected_count,
        "agents": ws_manager.get_all_agents_info()
    }
