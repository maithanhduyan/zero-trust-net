#!/usr/bin/env python3
"""
Zero Trust Hub Agent

Main daemon that:
1. Connects to Control Plane via WebSocket
2. Receives commands (add_peer, remove_peer, sync_peers)
3. Executes WireGuard and firewall operations
4. Reports status back to Control Plane
"""

import asyncio
import signal
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from websocket_handler import WebSocketHandler
from command_executor import CommandExecutor
from wireguard.manager import WireGuardManager
from wireguard.peer_manager import PeerManager
from firewall.iptables import HubFirewall
from firewall.forwarding import ForwardingManager
from status.interface_status import InterfaceStatus
from status.peer_stats import PeerStats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/hub-agent.log')
    ]
)
logger = logging.getLogger('hub-agent')


class HubAgent:
    """
    Hub Agent daemon - manages WireGuard server and receives commands from Control Plane
    """

    def __init__(
        self,
        control_plane_url: str = "ws://localhost:8000/api/v1/ws/hub",
        api_key: Optional[str] = None,
        interface: str = "wg0",
        config_dir: str = "/etc/wireguard",
        status_interval: int = 30,
    ):
        """
        Initialize Hub Agent

        Args:
            control_plane_url: WebSocket URL to Control Plane
            api_key: API key for authentication
            interface: WireGuard interface name
            config_dir: WireGuard config directory
            status_interval: Seconds between status reports
        """
        self.control_plane_url = control_plane_url
        self.api_key = api_key or os.environ.get("HUB_API_KEY", "")
        self.interface = interface
        self.config_dir = Path(config_dir)
        self.status_interval = status_interval

        # Components
        self.wg_manager = WireGuardManager(interface, config_dir)
        self.peer_manager = PeerManager(self.wg_manager)
        self.firewall = HubFirewall(interface)
        self.forwarding = ForwardingManager()
        self.interface_status = InterfaceStatus(interface)
        self.peer_stats = PeerStats(interface)

        # WebSocket handler
        self.ws_handler: Optional[WebSocketHandler] = None
        self.command_executor: Optional[CommandExecutor] = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

        logger.info(f"Hub Agent initialized for interface {interface}")

    async def start(self):
        """Start the Hub Agent daemon"""
        logger.info("Starting Hub Agent...")

        # Validate prerequisites
        if not self._validate_prerequisites():
            logger.error("Prerequisites check failed")
            sys.exit(1)

        # Ensure WireGuard interface is up
        if not await self.wg_manager.ensure_interface_up():
            logger.error(f"Failed to bring up {self.interface}")
            sys.exit(1)

        # Enable IP forwarding
        self.forwarding.enable_ip_forward()

        # Setup NAT masquerade
        await self.firewall.setup_masquerade()

        # Create command executor with all managers
        self.command_executor = CommandExecutor(
            wg_manager=self.wg_manager,
            peer_manager=self.peer_manager,
            firewall=self.firewall,
            interface_status=self.interface_status,
            peer_stats=self.peer_stats,
        )

        # Create WebSocket handler
        self.ws_handler = WebSocketHandler(
            url=self.control_plane_url,
            api_key=self.api_key,
            command_executor=self.command_executor,
        )

        self._running = True

        # Start tasks
        tasks = [
            asyncio.create_task(self._run_websocket()),
            asyncio.create_task(self._run_status_reporter()),
            asyncio.create_task(self._run_signal_handler()),
        ]

        logger.info("Hub Agent started successfully")

        # Wait for shutdown
        await self._shutdown_event.wait()

        # Cancel all tasks
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Hub Agent stopped")

    def _validate_prerequisites(self) -> bool:
        """Validate system prerequisites"""
        # Check if running as root
        if os.geteuid() != 0:
            logger.error("Hub Agent must run as root")
            return False

        # Check WireGuard tools
        if not self.wg_manager.check_wireguard_installed():
            logger.error("WireGuard tools not installed")
            return False

        # Check config exists
        config_file = self.config_dir / f"{self.interface}.conf"
        if not config_file.exists():
            logger.error(f"WireGuard config not found: {config_file}")
            return False

        # Check API key
        if not self.api_key:
            logger.error("HUB_API_KEY not set")
            return False

        return True

    async def _run_websocket(self):
        """Run WebSocket connection loop"""
        while self._running:
            try:
                await self.ws_handler.connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect delay

    async def _run_status_reporter(self):
        """Periodically report status to Control Plane"""
        while self._running:
            try:
                await asyncio.sleep(self.status_interval)

                if self.ws_handler and self.ws_handler.is_connected():
                    status = await self.interface_status.get_full_status()
                    await self.ws_handler.send_status(status)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Status reporter error: {e}")

    async def _run_signal_handler(self):
        """Handle shutdown signals"""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_shutdown)

        # Wait indefinitely (signals will trigger shutdown)
        await asyncio.Event().wait()

    def _signal_shutdown(self):
        """Handle shutdown signal"""
        logger.info("Received shutdown signal")
        self._running = False
        self._shutdown_event.set()

    async def stop(self):
        """Stop the Hub Agent"""
        logger.info("Stopping Hub Agent...")
        self._running = False
        self._shutdown_event.set()

        if self.ws_handler:
            await self.ws_handler.close()


def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Zero Trust Hub Agent")
    parser.add_argument(
        "--control-plane-url",
        default=os.environ.get("CONTROL_PLANE_URL", "ws://localhost:8000/api/v1/ws/hub"),
        help="WebSocket URL to Control Plane",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("HUB_API_KEY"),
        help="API key for authentication",
    )
    parser.add_argument(
        "--interface",
        default=os.environ.get("WG_INTERFACE", "wg0"),
        help="WireGuard interface name",
    )
    parser.add_argument(
        "--config-dir",
        default="/etc/wireguard",
        help="WireGuard config directory",
    )
    parser.add_argument(
        "--status-interval",
        type=int,
        default=30,
        help="Status report interval in seconds",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create and run agent
    agent = HubAgent(
        control_plane_url=args.control_plane_url,
        api_key=args.api_key,
        interface=args.interface,
        config_dir=args.config_dir,
        status_interval=args.status_interval,
    )

    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
