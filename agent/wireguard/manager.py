# agent/wireguard/manager.py
"""
WireGuard Interface Manager
Manages WireGuard interface lifecycle and peer configuration
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger('zt-agent.wireguard')


class WireGuardManager:
    """
    Manages WireGuard interface and configuration

    Responsibilities:
    - Generate and manage keypair
    - Bring interface up/down
    - Add/remove peers dynamically
    - Update peer configuration
    """

    def __init__(self, interface: str = "wg0", config_dir: str = "/etc/wireguard"):
        self.interface = interface
        self.config_dir = Path(config_dir)
        self.config_path = self.config_dir / f"{interface}.conf"
        self.private_key_path = self.config_dir / "private.key"
        self.public_key_path = self.config_dir / "public.key"

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Run shell command"""
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)

    def is_installed(self) -> bool:
        """Check if WireGuard is installed"""
        try:
            result = self._run(["which", "wg"], check=False)
            return result.returncode == 0
        except Exception:
            return False

    def keypair_exists(self) -> bool:
        """Check if keypair already exists"""
        return self.private_key_path.exists() and self.public_key_path.exists()

    def generate_keypair(self) -> tuple[str, str]:
        """
        Generate WireGuard keypair

        Returns:
            (private_key, public_key)
        """
        # Generate private key
        result = self._run(["wg", "genkey"])
        private_key = result.stdout.strip()

        # Save private key with restricted permissions
        self.private_key_path.write_text(private_key)
        os.chmod(self.private_key_path, 0o600)

        # Generate public key
        result = subprocess.run(
            ["wg", "pubkey"],
            input=private_key,
            capture_output=True,
            text=True,
            check=True
        )
        public_key = result.stdout.strip()

        # Save public key
        self.public_key_path.write_text(public_key)
        os.chmod(self.public_key_path, 0o644)

        logger.info(f"Generated keypair, public key: {public_key}")
        return private_key, public_key

    def get_private_key(self) -> Optional[str]:
        """Get private key"""
        if self.private_key_path.exists():
            return self.private_key_path.read_text().strip()
        return None

    def get_public_key(self) -> Optional[str]:
        """Get public key"""
        if self.public_key_path.exists():
            return self.public_key_path.read_text().strip()
        return None

    def is_up(self) -> bool:
        """Check if WireGuard interface is up"""
        result = self._run(["ip", "link", "show", self.interface], check=False)
        return result.returncode == 0 and "UP" in result.stdout

    def up(self) -> bool:
        """Bring WireGuard interface up"""
        if self.is_up():
            logger.info(f"{self.interface} is already up")
            return True

        try:
            self._run(["wg-quick", "up", self.interface])
            logger.info(f"Brought up {self.interface}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to bring up {self.interface}: {e.stderr}")
            return False

    def down(self) -> bool:
        """Bring WireGuard interface down"""
        if not self.is_up():
            logger.info(f"{self.interface} is already down")
            return True

        try:
            self._run(["wg-quick", "down", self.interface])
            logger.info(f"Brought down {self.interface}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to bring down {self.interface}: {e.stderr}")
            return False

    def restart(self) -> bool:
        """Restart WireGuard interface"""
        self.down()
        return self.up()

    def get_interface_info(self) -> Dict[str, Any]:
        """Get current interface status"""
        if not self.is_up():
            return {"status": "down"}

        try:
            result = self._run(["wg", "show", self.interface, "dump"])
            lines = result.stdout.strip().split('\n')

            if not lines:
                return {"status": "up", "peers": []}

            # Parse interface line
            interface_parts = lines[0].split('\t')
            info = {
                "status": "up",
                "private_key": interface_parts[0] if len(interface_parts) > 0 else None,
                "public_key": interface_parts[1] if len(interface_parts) > 1 else None,
                "listen_port": int(interface_parts[2]) if len(interface_parts) > 2 else None,
                "peers": []
            }

            # Parse peer lines
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) >= 4:
                    peer = {
                        "public_key": parts[0],
                        "endpoint": parts[2] if parts[2] != "(none)" else None,
                        "allowed_ips": parts[3],
                        "latest_handshake": int(parts[4]) if len(parts) > 4 else None,
                        "transfer_rx": int(parts[5]) if len(parts) > 5 else None,
                        "transfer_tx": int(parts[6]) if len(parts) > 6 else None
                    }
                    info["peers"].append(peer)

            return info

        except Exception as e:
            logger.error(f"Failed to get interface info: {e}")
            return {"status": "error", "error": str(e)}

    def add_peer(
        self,
        public_key: str,
        allowed_ips: str,
        endpoint: Optional[str] = None,
        persistent_keepalive: Optional[int] = None
    ) -> bool:
        """Add or update a peer"""
        try:
            cmd = ["wg", "set", self.interface, "peer", public_key, "allowed-ips", allowed_ips]

            if endpoint:
                cmd.extend(["endpoint", endpoint])

            if persistent_keepalive:
                cmd.extend(["persistent-keepalive", str(persistent_keepalive)])

            self._run(cmd)

            # Add route for the peer's IP
            ips = allowed_ips.split(',')
            for ip in ips:
                ip = ip.strip()
                if ip and not ip.endswith('/0'):
                    self._run(["ip", "route", "add", ip, "dev", self.interface], check=False)

            logger.info(f"Added/updated peer: {public_key[:20]}...")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add peer: {e.stderr}")
            return False

    def remove_peer(self, public_key: str) -> bool:
        """Remove a peer"""
        try:
            self._run(["wg", "set", self.interface, "peer", public_key, "remove"])
            logger.info(f"Removed peer: {public_key[:20]}...")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove peer: {e.stderr}")
            return False

    def update_peers(self, peers: List[Dict[str, Any]]) -> bool:
        """
        Update peers to match the provided list
        - Add new peers
        - Update existing peers
        - Remove peers not in the list
        """
        current_info = self.get_interface_info()
        current_peers = {p["public_key"]: p for p in current_info.get("peers", [])}
        new_peers = {p["public_key"]: p for p in peers}

        success = True

        # Add or update peers
        for pub_key, peer in new_peers.items():
            allowed_ips = peer.get("allowed_ips", "")
            if isinstance(allowed_ips, list):
                allowed_ips = ",".join(allowed_ips)

            if not self.add_peer(
                public_key=pub_key,
                allowed_ips=allowed_ips,
                endpoint=peer.get("endpoint"),
                persistent_keepalive=peer.get("persistent_keepalive")
            ):
                success = False

        # Remove peers not in the new list (except Hub which should always stay)
        for pub_key in current_peers:
            if pub_key not in new_peers:
                # Don't remove the hub peer
                peer = current_peers[pub_key]
                if peer.get("endpoint"):  # Hub has endpoint, spokes don't
                    logger.debug(f"Keeping hub peer: {pub_key[:20]}...")
                else:
                    if not self.remove_peer(pub_key):
                        success = False

        return success

    def get_stats(self) -> Dict[str, Any]:
        """Get interface statistics"""
        info = self.get_interface_info()

        if info.get("status") != "up":
            return {"status": info.get("status")}

        total_rx = sum(p.get("transfer_rx", 0) for p in info.get("peers", []))
        total_tx = sum(p.get("transfer_tx", 0) for p in info.get("peers", []))

        return {
            "status": "up",
            "peer_count": len(info.get("peers", [])),
            "total_rx_bytes": total_rx,
            "total_tx_bytes": total_tx,
            "total_rx_mb": round(total_rx / 1024 / 1024, 2),
            "total_tx_mb": round(total_tx / 1024 / 1024, 2)
        }
