"""
Hub Firewall (iptables) Manager

Manages firewall rules for Hub:
- NAT masquerade for VPN clients
- FORWARD chain rules
- Hub-level ACLs
"""

import asyncio
import subprocess
import logging
from typing import Optional

logger = logging.getLogger('hub-agent.firewall')


class HubFirewall:
    """
    Manages iptables rules for Hub server
    """

    # Chain names
    FORWARD_CHAIN = "ZT_HUB_FORWARD"
    NAT_CHAIN = "ZT_HUB_NAT"

    def __init__(self, interface: str = "wg0"):
        """
        Initialize firewall manager

        Args:
            interface: WireGuard interface name
        """
        self.interface = interface
        self._initialized = False

    async def initialize(self):
        """Initialize firewall chains"""
        if self._initialized:
            return

        # Create custom chains if they don't exist
        await self._create_chain("filter", self.FORWARD_CHAIN)
        await self._create_chain("nat", self.NAT_CHAIN)

        # Insert jump rules if not present
        await self._ensure_jump_rule("filter", "FORWARD", self.FORWARD_CHAIN)
        await self._ensure_jump_rule("nat", "POSTROUTING", self.NAT_CHAIN)

        self._initialized = True
        logger.info("Firewall chains initialized")

    async def setup_masquerade(self, outbound_interface: Optional[str] = None):
        """
        Setup NAT masquerade for VPN traffic

        Args:
            outbound_interface: Outbound interface (e.g., eth0).
                               If None, masquerade all.
        """
        await self.initialize()

        # Flush existing NAT rules
        await self._flush_chain("nat", self.NAT_CHAIN)

        # Add masquerade rule
        if outbound_interface:
            cmd = [
                "iptables", "-t", "nat", "-A", self.NAT_CHAIN,
                "-s", "10.10.0.0/24",  # VPN subnet
                "-o", outbound_interface,
                "-j", "MASQUERADE"
            ]
        else:
            cmd = [
                "iptables", "-t", "nat", "-A", self.NAT_CHAIN,
                "-s", "10.10.0.0/24",
                "!", "-o", self.interface,  # Not going back into VPN
                "-j", "MASQUERADE"
            ]

        await self._run_iptables(cmd)
        logger.info("NAT masquerade configured")

    async def setup_forwarding_rules(self):
        """Setup FORWARD chain rules for VPN traffic"""
        await self.initialize()

        # Flush existing forward rules
        await self._flush_chain("filter", self.FORWARD_CHAIN)

        # Allow established connections
        await self._run_iptables([
            "iptables", "-A", self.FORWARD_CHAIN,
            "-m", "state", "--state", "ESTABLISHED,RELATED",
            "-j", "ACCEPT"
        ])

        # Allow traffic from VPN interface
        await self._run_iptables([
            "iptables", "-A", self.FORWARD_CHAIN,
            "-i", self.interface,
            "-j", "ACCEPT"
        ])

        # Allow traffic to VPN interface
        await self._run_iptables([
            "iptables", "-A", self.FORWARD_CHAIN,
            "-o", self.interface,
            "-j", "ACCEPT"
        ])

        logger.info("Forwarding rules configured")

    async def add_acl_rule(
        self,
        action: str,
        source: Optional[str] = None,
        destination: Optional[str] = None,
        protocol: Optional[str] = None,
        port: Optional[int] = None,
        comment: Optional[str] = None,
    ):
        """
        Add an ACL rule

        Args:
            action: ACCEPT or DROP
            source: Source IP/CIDR
            destination: Destination IP/CIDR
            protocol: tcp, udp, icmp, etc.
            port: Destination port
            comment: Rule comment
        """
        await self.initialize()

        cmd = ["iptables", "-A", self.FORWARD_CHAIN]

        if source:
            cmd.extend(["-s", source])

        if destination:
            cmd.extend(["-d", destination])

        if protocol:
            cmd.extend(["-p", protocol])

            if port and protocol in ("tcp", "udp"):
                cmd.extend(["--dport", str(port)])

        if comment:
            cmd.extend(["-m", "comment", "--comment", comment])

        cmd.extend(["-j", action.upper()])

        await self._run_iptables(cmd)
        logger.debug(f"Added ACL rule: {action} {source or '*'} -> {destination or '*'}")

    async def clear_acl_rules(self):
        """Clear all ACL rules (flush custom chain)"""
        await self.initialize()
        await self._flush_chain("filter", self.FORWARD_CHAIN)
        # Re-add basic forwarding rules
        await self.setup_forwarding_rules()
        logger.info("ACL rules cleared")

    async def get_rules(self) -> list[str]:
        """Get list of current rules"""
        try:
            result = await asyncio.create_subprocess_exec(
                "iptables", "-L", self.FORWARD_CHAIN, "-n", "-v",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            return stdout.decode().strip().split('\n')
        except Exception as e:
            logger.error(f"Error getting rules: {e}")
            return []

    async def save_rules(self):
        """Save iptables rules to persist across reboots"""
        try:
            # Try iptables-save
            result = await asyncio.create_subprocess_shell(
                "iptables-save > /etc/iptables/rules.v4",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            if result.returncode == 0:
                logger.info("iptables rules saved")
            else:
                # Try netfilter-persistent
                await asyncio.create_subprocess_exec(
                    "netfilter-persistent", "save",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

        except Exception as e:
            logger.warning(f"Could not save iptables rules: {e}")

    # --- Private methods ---

    async def _create_chain(self, table: str, chain: str):
        """Create a chain if it doesn't exist"""
        # Check if chain exists
        result = await asyncio.create_subprocess_exec(
            "iptables", "-t", table, "-L", chain, "-n",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await result.communicate()

        if result.returncode != 0:
            # Chain doesn't exist, create it
            await self._run_iptables([
                "iptables", "-t", table, "-N", chain
            ])
            logger.debug(f"Created chain: {table}/{chain}")

    async def _ensure_jump_rule(self, table: str, parent_chain: str, target_chain: str):
        """Ensure jump rule exists in parent chain"""
        # Check if jump rule exists
        result = await asyncio.create_subprocess_exec(
            "iptables", "-t", table, "-C", parent_chain, "-j", target_chain,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await result.communicate()

        if result.returncode != 0:
            # Rule doesn't exist, add it
            await self._run_iptables([
                "iptables", "-t", table, "-I", parent_chain, "1", "-j", target_chain
            ])
            logger.debug(f"Added jump: {parent_chain} -> {target_chain}")

    async def _flush_chain(self, table: str, chain: str):
        """Flush all rules from a chain"""
        await self._run_iptables([
            "iptables", "-t", table, "-F", chain
        ])

    async def _run_iptables(self, cmd: list[str]) -> bool:
        """Run an iptables command"""
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.error(f"iptables failed: {' '.join(cmd)} - {stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"iptables error: {e}")
            return False
