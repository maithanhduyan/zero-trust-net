"""
WebSocket Handler for Hub Agent

Manages WebSocket connection to Control Plane:
- Authentication via API key
- Reconnection with exponential backoff
- Message routing to CommandExecutor
- Status reporting
"""

import asyncio
import json
import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    raise ImportError("websockets package required: pip install websockets")

if TYPE_CHECKING:
    from command_executor import CommandExecutor

logger = logging.getLogger('hub-agent.websocket')


class WebSocketHandler:
    """
    Handles WebSocket communication with Control Plane
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        command_executor: "CommandExecutor",
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        ping_interval: float = 30.0,
    ):
        """
        Initialize WebSocket handler

        Args:
            url: WebSocket URL (ws://localhost:8000/api/v1/ws/hub)
            api_key: API key for authentication
            command_executor: CommandExecutor instance
            reconnect_delay: Initial reconnect delay
            max_reconnect_delay: Maximum reconnect delay
            ping_interval: Ping keepalive interval
        """
        self.url = url
        self.api_key = api_key
        self.command_executor = command_executor
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.ping_interval = ping_interval

        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._current_delay = reconnect_delay

    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self._connected and self._ws is not None

    async def connect_and_listen(self):
        """Connect to Control Plane and listen for commands"""
        # Add API key to URL
        auth_url = f"{self.url}?api_key={self.api_key}"

        logger.info(f"Connecting to Control Plane: {self.url}")

        try:
            async with websockets.connect(
                auth_url,
                ping_interval=self.ping_interval,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                self._ws = ws
                self._connected = True
                self._current_delay = self.reconnect_delay  # Reset delay on success

                logger.info("Connected to Control Plane")

                # Send initial status
                await self._send_hello()

                # Listen for messages
                await self._listen_loop()

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self._connected = False
            self._ws = None

            # Exponential backoff
            await asyncio.sleep(self._current_delay)
            self._current_delay = min(
                self._current_delay * 2,
                self.max_reconnect_delay
            )

    async def _send_hello(self):
        """Send initial hello message with current status"""
        if not self._ws:
            return

        # Get current interface status
        status = await self.command_executor.get_interface_status()

        hello = {
            "type": "hello",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "interface_status": status,
        }

        await self._ws.send(json.dumps(hello))
        logger.debug("Sent hello message")

    async def _listen_loop(self):
        """Listen for incoming messages"""
        if not self._ws:
            return

        async for message in self._ws:
            try:
                await self._handle_message(message)
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    async def _handle_message(self, raw_message: str):
        """Handle incoming message from Control Plane"""
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {raw_message}")
            return

        msg_type = message.get("type")
        command_id = message.get("command_id")
        payload = message.get("payload", {})

        logger.debug(f"Received: {msg_type} (id={command_id})")

        # Route to command executor
        try:
            result = await self.command_executor.execute(msg_type, payload)

            # Send response
            response = {
                "type": "command_result",
                "command_id": command_id,
                "success": result.get("success", True),
                "data": result.get("data"),
                "error": result.get("error"),
                "timestamp": datetime.utcnow().isoformat(),
            }

            if self._ws:
                await self._ws.send(json.dumps(response))

        except Exception as e:
            logger.error(f"Command execution error: {e}")

            # Send error response
            error_response = {
                "type": "command_result",
                "command_id": command_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

            if self._ws:
                await self._ws.send(json.dumps(error_response))

    async def send_status(self, status: dict):
        """Send status update to Control Plane"""
        if not self._ws or not self._connected:
            logger.debug("Cannot send status: not connected")
            return

        message = {
            "type": "interface_status",
            "timestamp": datetime.utcnow().isoformat(),
            **status,
        }

        try:
            await self._ws.send(json.dumps(message))
            logger.debug("Sent status update")
        except Exception as e:
            logger.error(f"Failed to send status: {e}")

    async def send_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Send alert to Control Plane"""
        if not self._ws or not self._connected:
            return

        alert = {
            "type": "alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            await self._ws.send(json.dumps(alert))
            logger.info(f"Sent alert: {alert_type}")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    async def close(self):
        """Close WebSocket connection"""
        if self._ws:
            await self._ws.close()
            self._connected = False
            self._ws = None
            logger.info("WebSocket connection closed")
