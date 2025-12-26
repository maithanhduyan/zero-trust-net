# agent/wireguard/config_builder.py
"""
WireGuard Configuration Builder
Generates wg0.conf from Control Plane response
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger('zt-agent.wireguard.config')


class WireGuardConfigBuilder:
    """
    Builds WireGuard configuration file from API response

    Generates INI-style configuration for wg-quick
    """

    def __init__(self):
        pass

    def build_config(
        self,
        address: str,
        private_key_path: str,
        listen_port: int = 51820,
        dns: Optional[List[str]] = None,
        mtu: int = 1420,
        peers: Optional[List[Dict[str, Any]]] = None,
        post_up: Optional[List[str]] = None,
        post_down: Optional[List[str]] = None,
        table: str = "auto"
    ) -> str:
        """
        Build WireGuard configuration string

        Args:
            address: Overlay IP with CIDR (e.g., "10.0.0.2/24")
            private_key_path: Path to private key file
            listen_port: UDP port to listen on
            dns: List of DNS servers
            mtu: MTU for interface
            peers: List of peer configurations
            post_up: Commands to run after interface up
            post_down: Commands to run after interface down
            table: Routing table to use

        Returns:
            Configuration string
        """
        lines = []

        # [Interface] section
        lines.append("[Interface]")
        lines.append(f"Address = {address}")

        # Read private key from file
        lines.append(f"PrivateKey = {{PRIVATE_KEY}}")  # Placeholder

        if listen_port:
            lines.append(f"ListenPort = {listen_port}")

        if dns:
            lines.append(f"DNS = {', '.join(dns)}")

        if mtu:
            lines.append(f"MTU = {mtu}")

        if table != "auto":
            lines.append(f"Table = {table}")

        # PostUp commands (typically for firewall)
        if post_up:
            for cmd in post_up:
                lines.append(f"PostUp = {cmd}")

        # PostDown commands
        if post_down:
            for cmd in post_down:
                lines.append(f"PostDown = {cmd}")

        # [Peer] sections
        if peers:
            for peer in peers:
                lines.append("")
                lines.append("[Peer]")
                lines.append(f"PublicKey = {peer['public_key']}")

                if peer.get("preshared_key"):
                    lines.append(f"PresharedKey = {peer['preshared_key']}")

                allowed_ips = peer.get("allowed_ips", "")
                if isinstance(allowed_ips, list):
                    allowed_ips = ", ".join(allowed_ips)
                lines.append(f"AllowedIPs = {allowed_ips}")

                if peer.get("endpoint"):
                    lines.append(f"Endpoint = {peer['endpoint']}")

                if peer.get("persistent_keepalive"):
                    lines.append(f"PersistentKeepalive = {peer['persistent_keepalive']}")

        config = "\n".join(lines) + "\n"

        # Replace private key placeholder with actual key
        if os.path.exists(private_key_path):
            with open(private_key_path, 'r') as f:
                private_key = f.read().strip()
            config = config.replace("{PRIVATE_KEY}", private_key)

        return config

    def build_from_api_response(self, response: Dict[str, Any], private_key_path: str) -> str:
        """
        Build configuration from Control Plane API response

        Expected response format:
        {
            "interface": {
                "address": "10.0.0.2/24",
                "listen_port": 51820,
                "dns": ["10.0.0.1"],
                "mtu": 1420
            },
            "peers": [
                {
                    "public_key": "...",
                    "endpoint": "1.2.3.4:51820",
                    "allowed_ips": ["10.0.0.1/32", "10.0.0.0/24"],
                    "persistent_keepalive": 25
                }
            ]
        }
        """
        interface = response.get("interface", {})
        peers = response.get("peers", [])

        return self.build_config(
            address=interface.get("address", response.get("overlay_ip", "10.0.0.2/24")),
            private_key_path=private_key_path,
            listen_port=interface.get("listen_port", 51820),
            dns=interface.get("dns"),
            mtu=interface.get("mtu", 1420),
            peers=peers
        )

    def write_config(self, config: str, path: Path, backup: bool = True) -> bool:
        """
        Write configuration to file

        Args:
            config: Configuration string
            path: Path to write to
            backup: Whether to backup existing config

        Returns:
            Success status
        """
        try:
            path = Path(path)

            # Backup existing config
            if backup and path.exists():
                backup_path = path.with_suffix('.conf.bak')
                path.rename(backup_path)
                logger.info(f"Backed up existing config to {backup_path}")

            # Write new config with restricted permissions
            path.write_text(config)
            os.chmod(path, 0o600)

            logger.info(f"Wrote WireGuard config to {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write config: {e}")
            return False

    def parse_config(self, path: Path) -> Dict[str, Any]:
        """
        Parse an existing WireGuard config file

        Returns:
            Parsed configuration as dict
        """
        path = Path(path)
        if not path.exists():
            return {}

        content = path.read_text()
        config = {
            "interface": {},
            "peers": []
        }

        current_section = None
        current_peer = {}

        for line in content.split('\n'):
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            if line == "[Interface]":
                current_section = "interface"
                continue

            if line == "[Peer]":
                if current_peer:
                    config["peers"].append(current_peer)
                current_section = "peer"
                current_peer = {}
                continue

            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()

                if current_section == "interface":
                    config["interface"][key] = value
                elif current_section == "peer":
                    current_peer[key] = value

        # Don't forget last peer
        if current_peer:
            config["peers"].append(current_peer)

        return config


def generate_hub_config(
    private_key_path: str,
    address: str = "10.0.0.1/24",
    listen_port: int = 51820,
    save_iptables: bool = True
) -> str:
    """
    Generate configuration for Hub node

    Hub has special PostUp/PostDown for NAT and forwarding
    """
    builder = WireGuardConfigBuilder()

    post_up = [
        "iptables -A FORWARD -i %i -j ACCEPT",
        "iptables -A FORWARD -o %i -j ACCEPT",
        "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
    ]

    post_down = [
        "iptables -D FORWARD -i %i -j ACCEPT",
        "iptables -D FORWARD -o %i -j ACCEPT",
        "iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
    ]

    if save_iptables:
        post_up.append("iptables-save > /etc/iptables.rules")

    return builder.build_config(
        address=address,
        private_key_path=private_key_path,
        listen_port=listen_port,
        mtu=1420,
        peers=[],  # Peers will be added dynamically
        post_up=post_up,
        post_down=post_down
    )
