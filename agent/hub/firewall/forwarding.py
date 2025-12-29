"""
IP Forwarding Manager for Hub

Manages Linux kernel IP forwarding settings:
- Enable/disable IPv4 forwarding
- Enable/disable IPv6 forwarding
- Persist settings
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger('hub-agent.forwarding')


class ForwardingManager:
    """
    Manages IP forwarding settings
    """

    # sysctl paths
    IPV4_FORWARD = "/proc/sys/net/ipv4/ip_forward"
    IPV6_FORWARD = "/proc/sys/net/ipv6/conf/all/forwarding"
    SYSCTL_CONF = "/etc/sysctl.d/99-zerotrust.conf"

    def __init__(self, enable_ipv6: bool = False):
        """
        Initialize forwarding manager

        Args:
            enable_ipv6: Whether to also manage IPv6 forwarding
        """
        self.enable_ipv6 = enable_ipv6

    def enable_ip_forward(self, persist: bool = True):
        """
        Enable IP forwarding

        Args:
            persist: Whether to persist across reboots
        """
        # Enable IPv4 forwarding
        self._write_sysctl(self.IPV4_FORWARD, "1")
        logger.info("IPv4 forwarding enabled")

        # Enable IPv6 forwarding if requested
        if self.enable_ipv6:
            self._write_sysctl(self.IPV6_FORWARD, "1")
            logger.info("IPv6 forwarding enabled")

        # Persist settings
        if persist:
            self._persist_settings()

    def disable_ip_forward(self, persist: bool = True):
        """
        Disable IP forwarding

        Args:
            persist: Whether to persist across reboots
        """
        self._write_sysctl(self.IPV4_FORWARD, "0")
        logger.info("IPv4 forwarding disabled")

        if self.enable_ipv6:
            self._write_sysctl(self.IPV6_FORWARD, "0")
            logger.info("IPv6 forwarding disabled")

        if persist:
            self._remove_persist_settings()

    def is_forwarding_enabled(self) -> bool:
        """Check if IPv4 forwarding is enabled"""
        try:
            with open(self.IPV4_FORWARD, 'r') as f:
                return f.read().strip() == "1"
        except Exception:
            return False

    def _write_sysctl(self, path: str, value: str):
        """Write to sysctl file"""
        try:
            with open(path, 'w') as f:
                f.write(value)
        except PermissionError:
            logger.error(f"Permission denied writing to {path}")
            raise
        except Exception as e:
            logger.error(f"Error writing to {path}: {e}")
            raise

    def _persist_settings(self):
        """Persist forwarding settings to sysctl.d"""
        try:
            config_lines = [
                "# Zero Trust Hub IP Forwarding",
                "net.ipv4.ip_forward = 1",
            ]

            if self.enable_ipv6:
                config_lines.append("net.ipv6.conf.all.forwarding = 1")

            # Ensure directory exists
            Path(self.SYSCTL_CONF).parent.mkdir(parents=True, exist_ok=True)

            with open(self.SYSCTL_CONF, 'w') as f:
                f.write('\n'.join(config_lines) + '\n')

            os.chmod(self.SYSCTL_CONF, 0o644)
            logger.info(f"Forwarding settings persisted to {self.SYSCTL_CONF}")

        except Exception as e:
            logger.warning(f"Could not persist settings: {e}")

    def _remove_persist_settings(self):
        """Remove persisted forwarding settings"""
        try:
            if Path(self.SYSCTL_CONF).exists():
                os.remove(self.SYSCTL_CONF)
                logger.info(f"Removed {self.SYSCTL_CONF}")
        except Exception as e:
            logger.warning(f"Could not remove settings file: {e}")
