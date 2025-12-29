"""
WireGuard Manager for Hub Agent

Manages WireGuard interface in SERVER mode:
- No Endpoint (hub accepts connections)
- ListenPort configured
- Interface up/down/restart
- Peer add/remove via wg command
"""

import asyncio
import subprocess
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger('hub-agent.wireguard')


class WireGuardManager:
    """
    Manages WireGuard interface for Hub (server mode)
    """

    def __init__(self, interface: str = "wg0", config_dir: str = "/etc/wireguard"):
        """
        Initialize WireGuard manager

        Args:
            interface: WireGuard interface name
            config_dir: Config directory path
        """
        self.interface = interface
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / f"{interface}.conf"

    def check_wireguard_installed(self) -> bool:
        """Check if WireGuard tools are installed"""
        try:
            result = subprocess.run(
                ["wg", "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    async def ensure_interface_up(self) -> bool:
        """Ensure WireGuard interface is up"""
        if await self.is_interface_up():
            logger.debug(f"{self.interface} is already up")
            return True

        return await self.bring_up_interface()

    async def is_interface_up(self) -> bool:
        """Check if interface is up"""
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking interface: {e}")
            return False

    async def bring_up_interface(self) -> bool:
        """Bring up WireGuard interface using wg-quick"""
        logger.info(f"Bringing up {self.interface}")

        try:
            result = await asyncio.create_subprocess_exec(
                "wg-quick", "up", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                logger.info(f"{self.interface} is now up")
                return True
            else:
                logger.error(f"Failed to bring up {self.interface}: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Error bringing up interface: {e}")
            return False

    async def bring_down_interface(self) -> bool:
        """Bring down WireGuard interface"""
        logger.info(f"Bringing down {self.interface}")

        try:
            result = await asyncio.create_subprocess_exec(
                "wg-quick", "down", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Error bringing down interface: {e}")
            return False

    async def restart_interface(self) -> bool:
        """Restart WireGuard interface"""
        logger.info(f"Restarting {self.interface}")

        await self.bring_down_interface()
        await asyncio.sleep(1)
        return await self.bring_up_interface()

    async def add_peer(
        self,
        public_key: str,
        allowed_ips: str,
        preshared_key: Optional[str] = None,
        persistent_keepalive: int = 0,
    ) -> bool:
        """
        Add a peer to WireGuard interface

        Args:
            public_key: Peer's public key
            allowed_ips: Allowed IPs (e.g., "10.10.0.5/32")
            preshared_key: Optional preshared key
            persistent_keepalive: Keepalive interval

        Returns:
            True if successful
        """
        cmd = ["wg", "set", self.interface, "peer", public_key, "allowed-ips", allowed_ips]

        if preshared_key:
            # Use stdin for preshared key
            cmd.extend(["preshared-key", "/dev/stdin"])

        if persistent_keepalive > 0:
            cmd.extend(["persistent-keepalive", str(persistent_keepalive)])

        try:
            if preshared_key:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await result.communicate(input=preshared_key.encode())
            else:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await result.communicate()

            if result.returncode == 0:
                logger.debug(f"Added peer: {public_key[:16]}...")
                # Save config to persist
                await self.save_config()
                return True
            else:
                logger.error(f"Failed to add peer: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Error adding peer: {e}")
            return False

    async def remove_peer(self, public_key: str) -> bool:
        """
        Remove a peer from WireGuard interface

        Args:
            public_key: Peer's public key

        Returns:
            True if successful
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "set", self.interface, "peer", public_key, "remove",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                logger.debug(f"Removed peer: {public_key[:16]}...")
                await self.save_config()
                return True
            else:
                logger.error(f"Failed to remove peer: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Error removing peer: {e}")
            return False

    async def save_config(self) -> bool:
        """Save current WireGuard config to file"""
        try:
            result = await asyncio.create_subprocess_exec(
                "wg-quick", "save", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            if result.returncode == 0:
                logger.debug("Config saved")
                return True
            else:
                # wg-quick save may not be available, try manual save
                return await self._manual_save_config()

        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    async def _manual_save_config(self) -> bool:
        """Manually save WireGuard config"""
        try:
            # Get current interface config
            result = await asyncio.create_subprocess_exec(
                "wg", "showconf", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.error(f"Failed to get config: {stderr.decode()}")
                return False

            # Read existing config to preserve Address, PostUp, PostDown
            existing_config = {}
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            if key in ['Address', 'PostUp', 'PostDown', 'DNS', 'MTU']:
                                existing_config[key] = value.strip()

            # Merge configs
            wg_config = stdout.decode()

            # Insert preserved settings after [Interface]
            if existing_config:
                lines = wg_config.split('\n')
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if line.strip() == '[Interface]':
                        for key, value in existing_config.items():
                            new_lines.append(f"{key} = {value}")
                wg_config = '\n'.join(new_lines)

            # Write config
            with open(self.config_file, 'w') as f:
                f.write(wg_config)

            os.chmod(self.config_file, 0o600)
            logger.debug("Config saved manually")
            return True

        except Exception as e:
            logger.error(f"Error manual saving config: {e}")
            return False

    async def get_peers(self) -> list[dict]:
        """
        Get list of current peers

        Returns:
            List of peer dicts with public_key, allowed_ips, etc.
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface, "dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.error(f"Failed to get peers: {stderr.decode()}")
                return []

            peers = []
            lines = stdout.decode().strip().split('\n')

            # First line is interface info, skip it
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 4:
                    peers.append({
                        "public_key": parts[0],
                        "preshared_key": parts[1] if parts[1] != "(none)" else None,
                        "endpoint": parts[2] if parts[2] != "(none)" else None,
                        "allowed_ips": parts[3],
                        "latest_handshake": int(parts[4]) if len(parts) > 4 and parts[4] != "0" else None,
                        "transfer_rx": int(parts[5]) if len(parts) > 5 else 0,
                        "transfer_tx": int(parts[6]) if len(parts) > 6 else 0,
                        "persistent_keepalive": parts[7] if len(parts) > 7 and parts[7] != "off" else None,
                    })

            return peers

        except Exception as e:
            logger.error(f"Error getting peers: {e}")
            return []

    async def get_interface_info(self) -> dict:
        """
        Get interface information

        Returns:
            Dict with interface info (public_key, listen_port, etc.)
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface, "dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                return {}

            lines = stdout.decode().strip().split('\n')
            if lines:
                parts = lines[0].split('\t')
                if len(parts) >= 3:
                    return {
                        "private_key": "(hidden)",
                        "public_key": parts[1],
                        "listen_port": int(parts[2]) if parts[2] else None,
                        "fwmark": parts[3] if len(parts) > 3 else None,
                    }

            return {}

        except Exception as e:
            logger.error(f"Error getting interface info: {e}")
            return {}
