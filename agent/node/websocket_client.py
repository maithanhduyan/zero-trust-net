# agent/node/websocket_client.py
"""
WebSocket Client for Node Agent - Real-time Communication with Control Plane

Provides:
- Persistent WebSocket connection to Control Plane
- Automatic reconnection with exponential backoff
- Heartbeat ping/pong for keepalive
- Fallback to HTTP polling if WebSocket fails
"""

import asyncio
import json
import logging
import ssl
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger('zt-agent.websocket')


class ConnectionState(Enum):
    """WebSocket connection state"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class WebSocketConfig:
    """WebSocket client configuration"""
    base_url: str
    hostname: str
    public_key: str
    ping_interval: int = 30  # seconds
    reconnect_min_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    reconnect_factor: float = 2.0
    max_reconnect_attempts: int = 0  # 0 = unlimited


class WebSocketClient:
    """
    Async WebSocket client for Control Plane communication

    Features:
    - Automatic reconnection with exponential backoff
    - Ping/pong keepalive
    - Message handlers for different event types
    - Connection state tracking
    """

    def __init__(self, config: WebSocketConfig):
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self._websocket = None
        self._handlers: Dict[str, Callable] = {}
        self._reconnect_delay = config.reconnect_min_delay
        self._reconnect_attempts = 0
        self._running = False
        self._last_pong: Optional[datetime] = None

        # Default handlers
        self._on_connected: Optional[Callable] = None
        self._on_disconnected: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def on_message(self, msg_type: str):
        """Decorator to register message handler"""
        def decorator(func: Callable):
            self._handlers[msg_type] = func
            return func
        return decorator

    def set_connected_handler(self, handler: Callable):
        self._on_connected = handler

    def set_disconnected_handler(self, handler: Callable):
        self._on_disconnected = handler

    def set_error_handler(self, handler: Callable):
        self._on_error = handler

    def _get_ws_url(self) -> str:
        """Build WebSocket URL"""
        base = self.config.base_url.replace("http://", "ws://").replace("https://", "wss://")
        from urllib.parse import quote
        encoded_key = quote(self.config.public_key, safe='')
        return f"{base}/api/v1/ws/agent/{self.config.hostname}?public_key={encoded_key}"

    async def connect(self) -> bool:
        """
        Establish WebSocket connection

        Returns True if connected successfully, False otherwise
        """
        try:
            import websockets
        except ImportError:
            logger.warning("websockets package not installed. Install with: pip install websockets")
            return False

        self.state = ConnectionState.CONNECTING
        ws_url = self._get_ws_url()

        try:
            logger.info(f"Connecting to WebSocket: {ws_url.split('?')[0]}...")

            # SSL context for wss://
            ssl_context = None
            if ws_url.startswith("wss://"):
                ssl_context = ssl.create_default_context()
                # In development, may need to disable cert verification
                # ssl_context.check_hostname = False
                # ssl_context.verify_mode = ssl.CERT_NONE

            self._websocket = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                ping_interval=None,  # We handle our own pings
                ping_timeout=None
            )

            self.state = ConnectionState.CONNECTED
            self._reconnect_delay = self.config.reconnect_min_delay
            self._reconnect_attempts = 0
            self._last_pong = datetime.utcnow()

            logger.info("WebSocket connected successfully")

            if self._on_connected:
                await self._call_handler(self._on_connected)

            return True

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.state = ConnectionState.DISCONNECTED
            if self._on_error:
                await self._call_handler(self._on_error, e)
            return False

    async def disconnect(self):
        """Close WebSocket connection"""
        self._running = False
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
        self._websocket = None
        self.state = ConnectionState.DISCONNECTED
        logger.info("WebSocket disconnected")

    async def send(self, message: Dict[str, Any]) -> bool:
        """Send message to Control Plane"""
        if not self.is_connected or not self._websocket:
            logger.warning("Cannot send: not connected")
            return False

        try:
            await self._websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_heartbeat(
        self,
        metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send heartbeat with optional metrics"""
        message = {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat()
        }
        if metrics:
            message["metrics"] = metrics
        return await self.send(message)

    async def send_ping(self) -> bool:
        """Send keepalive ping"""
        return await self.send({"type": "ping"})

    async def _call_handler(self, handler: Callable, *args):
        """Call handler (sync or async)"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(*args)
            else:
                handler(*args)
        except Exception as e:
            logger.error(f"Handler error: {e}")

    async def _handle_message(self, raw_message: str):
        """Process incoming message"""
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type")

            if msg_type == "pong":
                self._last_pong = datetime.utcnow()
                logger.debug("Received pong")
                return

            if msg_type == "heartbeat_ack":
                logger.debug("Heartbeat acknowledged")
                return

            # Dispatch to registered handler
            if msg_type in self._handlers:
                await self._call_handler(self._handlers[msg_type], message)
            else:
                logger.debug(f"No handler for message type: {msg_type}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {raw_message[:100]}")

    async def _receive_loop(self):
        """Receive and process messages"""
        import websockets

        while self._running and self.is_connected:
            try:
                message = await asyncio.wait_for(
                    self._websocket.recv(),
                    timeout=self.config.ping_interval + 10
                )
                await self._handle_message(message)

            except asyncio.TimeoutError:
                # Check connection health
                if self._last_pong:
                    since_pong = (datetime.utcnow() - self._last_pong).total_seconds()
                    if since_pong > self.config.ping_interval * 2:
                        logger.warning("No pong received, connection may be dead")
                        break

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}")
                break

            except Exception as e:
                logger.error(f"Receive error: {e}")
                break

        self.state = ConnectionState.DISCONNECTED

    async def _ping_loop(self):
        """Send periodic pings"""
        while self._running and self.is_connected:
            await asyncio.sleep(self.config.ping_interval)
            if self.is_connected:
                await self.send_ping()

    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        self.state = ConnectionState.RECONNECTING

        while self._running:
            max_attempts = self.config.max_reconnect_attempts
            if max_attempts > 0 and self._reconnect_attempts >= max_attempts:
                logger.error(f"Max reconnection attempts ({max_attempts}) reached")
                return False

            self._reconnect_attempts += 1
            logger.info(f"Reconnection attempt {self._reconnect_attempts} in {self._reconnect_delay:.1f}s...")

            await asyncio.sleep(self._reconnect_delay)

            if await self.connect():
                return True

            # Exponential backoff
            self._reconnect_delay = min(
                self._reconnect_delay * self.config.reconnect_factor,
                self.config.reconnect_max_delay
            )

        return False

    async def run(self):
        """
        Main run loop - connect and maintain connection

        This is the primary entry point for the WebSocket client.
        Call this in an async context to start the client.
        """
        self._running = True

        while self._running:
            # Connect if not connected
            if not self.is_connected:
                if not await self.connect():
                    if not await self._reconnect():
                        break
                    continue

            # Run receive and ping loops
            try:
                receive_task = asyncio.create_task(self._receive_loop())
                ping_task = asyncio.create_task(self._ping_loop())

                # Wait for either to complete (usually due to disconnect)
                done, pending = await asyncio.wait(
                    [receive_task, ping_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            except Exception as e:
                logger.error(f"Run loop error: {e}")

            # If we get here, we disconnected
            if self._running:
                if self._on_disconnected:
                    await self._call_handler(self._on_disconnected)

                # Try to reconnect
                if not await self._reconnect():
                    break

        self.state = ConnectionState.DISCONNECTED


class HybridClient:
    """
    Hybrid client that uses WebSocket with HTTP fallback

    - Attempts WebSocket connection first
    - Falls back to HTTP polling if WebSocket unavailable
    - Automatically switches back to WebSocket when available
    """

    def __init__(
        self,
        base_url: str,
        hostname: str,
        public_key: str,
        poll_interval: int = 60,
        websocket_enabled: bool = True
    ):
        self.base_url = base_url
        self.hostname = hostname
        self.public_key = public_key
        self.poll_interval = poll_interval
        self.websocket_enabled = websocket_enabled

        self._ws_client: Optional[WebSocketClient] = None
        self._http_client = None  # Will be imported from client.py
        self._config_callback: Optional[Callable] = None
        self._running = False

    @property
    def is_websocket_connected(self) -> bool:
        return self._ws_client is not None and self._ws_client.is_connected

    def on_config_update(self, callback: Callable):
        """Register callback for config updates"""
        self._config_callback = callback

    async def _handle_config_updated(self, message: Dict[str, Any]):
        """Handle config_updated message from WebSocket"""
        logger.info("Received config update notification")
        if self._config_callback:
            # Fetch new config via HTTP
            try:
                from .client import ControlPlaneClient
                http = ControlPlaneClient(self.base_url)
                config = http.get_config(self.hostname)
                await self._call_callback(config)
            except Exception as e:
                logger.error(f"Failed to fetch config after update: {e}")

    async def _call_callback(self, config: Dict[str, Any]):
        """Call config callback"""
        if self._config_callback:
            if asyncio.iscoroutinefunction(self._config_callback):
                await self._config_callback(config)
            else:
                self._config_callback(config)

    async def _poll_config(self):
        """Poll for config updates via HTTP"""
        from .client import ControlPlaneClient
        http = ControlPlaneClient(self.base_url)
        last_version = 0

        while self._running and not self.is_websocket_connected:
            try:
                config = http.get_config(self.hostname)
                version = config.get("config_version", 0)

                if version > last_version:
                    logger.info(f"Config updated: version {last_version} -> {version}")
                    await self._call_callback(config)
                    last_version = version

            except Exception as e:
                logger.error(f"Polling failed: {e}")

            await asyncio.sleep(self.poll_interval)

    async def run(self):
        """
        Run hybrid client

        - Try WebSocket first
        - Fall back to polling if WebSocket fails
        - Retry WebSocket periodically
        """
        self._running = True

        if self.websocket_enabled:
            # Try to use WebSocket
            try:
                import websockets  # Check if available

                ws_config = WebSocketConfig(
                    base_url=self.base_url,
                    hostname=self.hostname,
                    public_key=self.public_key
                )
                self._ws_client = WebSocketClient(ws_config)

                # Register config update handler
                @self._ws_client.on_message("config_updated")
                async def on_config_updated(msg):
                    await self._handle_config_updated(msg)

                # Run WebSocket client (will reconnect automatically)
                await self._ws_client.run()

            except ImportError:
                logger.warning("websockets not installed, using HTTP polling only")
                self._ws_client = None

        # WebSocket not available or failed, use polling
        if not self.is_websocket_connected:
            logger.info(f"Using HTTP polling (interval: {self.poll_interval}s)")
            await self._poll_config()

    def stop(self):
        """Stop the client"""
        self._running = False
        if self._ws_client:
            asyncio.create_task(self._ws_client.disconnect())
