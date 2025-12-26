#!/usr/bin/env python3
# agent/agent.py
"""
Zero Trust Agent Daemon
Runs on each VPS to sync configuration from Control Plane
"""

import os
import sys
import time
import signal
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

from client import ControlPlaneClient
from wireguard.manager import WireGuardManager
from wireguard.config_builder import WireGuardConfigBuilder
from firewall.iptables import IPTablesManager
from collectors.host_info import collect_host_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/zt-agent.log')
    ]
)
logger = logging.getLogger('zt-agent')


class ZeroTrustAgent:
    """
    Zero Trust Agent - Main daemon class

    Responsibilities:
    1. Register with Control Plane on first run
    2. Sync configuration periodically
    3. Apply WireGuard configuration
    4. Apply firewall rules (ACLs)
    """

    def __init__(
        self,
        hostname: str,
        role: str,
        control_plane_url: str,
        sync_interval: int = 60,
        config_dir: str = "/etc/wireguard"
    ):
        self.hostname = hostname
        self.role = role
        self.sync_interval = sync_interval
        self.config_dir = Path(config_dir)
        self.running = True

        # Initialize components
        self.client = ControlPlaneClient(control_plane_url)
        self.wg_manager = WireGuardManager(interface="wg0", config_dir=config_dir)
        self.wg_builder = WireGuardConfigBuilder()
        self.firewall = IPTablesManager(interface="wg0")

        # State tracking
        self.registered = False
        self.overlay_ip: Optional[str] = None
        self.current_config_version = 0
        self.public_key: Optional[str] = None

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def initialize(self) -> bool:
        """
        Initialize the agent
        - Ensure WireGuard is installed
        - Generate keypair if not exists
        - Register with Control Plane
        """
        logger.info(f"Initializing Zero Trust Agent for {self.hostname}")

        # 1. Check WireGuard installation
        if not self.wg_manager.is_installed():
            logger.error("WireGuard is not installed. Please install wireguard-tools.")
            return False

        # 2. Ensure keypair exists
        if not self.wg_manager.keypair_exists():
            logger.info("Generating WireGuard keypair...")
            self.wg_manager.generate_keypair()

        self.public_key = self.wg_manager.get_public_key()
        logger.info(f"Public key: {self.public_key}")

        # 3. Register with Control Plane
        return self.register()

    def register(self) -> bool:
        """Register this node with the Control Plane"""
        logger.info(f"Registering with Control Plane as {self.hostname} (role: {self.role})")

        # Collect host info
        host_info = collect_host_info()

        try:
            response = self.client.register(
                hostname=self.hostname,
                role=self.role,
                public_key=self.public_key,
                agent_version="1.0.0",
                os_info=host_info.get("os_info", "Unknown")
            )

            self.overlay_ip = response.get("overlay_ip")
            self.registered = True

            logger.info(f"Registration successful! Overlay IP: {self.overlay_ip}")
            logger.info(f"Status: {response.get('status')}")

            # Initial WireGuard setup
            self._setup_initial_wireguard(response)

            return True

        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return False

    def _setup_initial_wireguard(self, registration_response: dict):
        """Setup initial WireGuard configuration after registration"""
        config = self.wg_builder.build_config(
            address=registration_response["overlay_ip"],
            private_key_path=str(self.config_dir / "private.key"),
            dns=registration_response.get("dns_servers", ["10.0.0.1"]),
            peers=[{
                "public_key": registration_response["hub_public_key"],
                "endpoint": registration_response["hub_endpoint"],
                "allowed_ips": registration_response.get("allowed_ips", "10.0.0.0/24"),
                "persistent_keepalive": 25
            }]
        )

        # Write config
        config_path = self.config_dir / "wg0.conf"
        self.wg_builder.write_config(config, config_path)

        # Start WireGuard
        self.wg_manager.up()
        logger.info("WireGuard interface wg0 is up")

    def sync_config(self) -> bool:
        """
        Sync configuration from Control Plane
        - Get latest peers and ACL rules
        - Apply changes if config version changed
        """
        if not self.registered:
            logger.warning("Not registered, skipping sync")
            return False

        try:
            # Get config from Control Plane
            config = self.client.get_config(self.hostname)

            # Check if config changed
            new_version = config.get("config_version", 0)

            if new_version > self.current_config_version:
                logger.info(f"Config changed: v{self.current_config_version} -> v{new_version}")
                self._apply_config(config)
                self.current_config_version = new_version
            else:
                logger.debug("Config unchanged")

            return True

        except Exception as e:
            logger.error(f"Config sync failed: {e}")
            return False

    def _apply_config(self, config: dict):
        """Apply configuration changes"""
        # 1. Update WireGuard peers if changed
        peers = config.get("peers", [])
        if peers:
            logger.info(f"Updating WireGuard peers ({len(peers)} peers)")
            self.wg_manager.update_peers(peers)

        # 2. Apply firewall rules
        acl_rules = config.get("acl_rules", [])
        logger.info(f"Applying {len(acl_rules)} ACL rules")
        self.firewall.apply_rules(acl_rules)

    def send_heartbeat(self) -> bool:
        """Send heartbeat to Control Plane"""
        try:
            response = self.client.heartbeat(
                hostname=self.hostname,
                public_key=self.public_key
            )

            # Check if config changed
            if response.get("config_changed"):
                logger.info("Control Plane indicates config changed, syncing...")
                self.sync_config()

            return True

        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            return False

    def run(self):
        """Main daemon loop"""
        logger.info("Starting Zero Trust Agent daemon")

        # Initialize
        if not self.initialize():
            logger.error("Initialization failed, exiting")
            sys.exit(1)

        # Wait for node approval if pending
        while self.running:
            try:
                config = self.client.get_config(self.hostname)
                if config.get("status") == "active":
                    logger.info("Node is active, starting sync loop")
                    break
                else:
                    logger.info(f"Node status: {config.get('status')}. Waiting for approval...")
                    time.sleep(10)
            except Exception as e:
                if "403" in str(e):
                    logger.info("Node pending approval, waiting...")
                    time.sleep(10)
                else:
                    logger.error(f"Error checking status: {e}")
                    time.sleep(30)

        # Main loop
        last_sync = 0
        heartbeat_interval = 30
        last_heartbeat = 0

        while self.running:
            now = time.time()

            # Sync config
            if now - last_sync >= self.sync_interval:
                self.sync_config()
                last_sync = now

            # Send heartbeat
            if now - last_heartbeat >= heartbeat_interval:
                self.send_heartbeat()
                last_heartbeat = now

            # Sleep
            time.sleep(1)

        # Cleanup
        logger.info("Agent shutting down")
        self.cleanup()

    def cleanup(self):
        """Cleanup on shutdown"""
        logger.info("Cleaning up...")
        # Optionally bring down WireGuard
        # self.wg_manager.down()


def main():
    parser = argparse.ArgumentParser(description="Zero Trust Agent")
    parser.add_argument("--hostname", required=True, help="Node hostname")
    parser.add_argument("--role", required=True, choices=["hub", "app", "db", "ops", "monitor"], help="Node role")
    parser.add_argument("--control-plane", default="https://hub.example.com", help="Control Plane URL")
    parser.add_argument("--sync-interval", type=int, default=60, help="Config sync interval in seconds")
    parser.add_argument("--config-dir", default="/etc/wireguard", help="WireGuard config directory")

    args = parser.parse_args()

    agent = ZeroTrustAgent(
        hostname=args.hostname,
        role=args.role,
        control_plane_url=args.control_plane,
        sync_interval=args.sync_interval,
        config_dir=args.config_dir
    )

    agent.run()


if __name__ == "__main__":
    main()
