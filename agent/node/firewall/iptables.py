# agent/node/firewall/iptables.py
"""
IPTables Manager for Node Agent
Applies Zero Trust ACL rules via iptables
"""

import subprocess
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger('zt-agent.firewall')


class IPTablesManager:
    """
    Manages iptables rules for Zero Trust ACL enforcement

    Creates a dedicated chain for ZT rules that can be flushed
    and rebuilt on config sync without affecting other rules.
    """

    CHAIN_NAME = "ZT_ACL"

    def __init__(self, interface: str = "wg0"):
        self.interface = interface
        self._ensure_chain_exists()

    def _run(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run iptables command"""
        logger.debug(f"iptables: {' '.join(cmd)}")
        return subprocess.run(cmd, check=check, capture_output=True, text=True)

    def _ensure_chain_exists(self):
        """Ensure the ZT_ACL chain exists"""
        try:
            # Check if chain exists
            result = self._run(["iptables", "-L", self.CHAIN_NAME, "-n"], check=False)

            if result.returncode != 0:
                # Create chain
                self._run(["iptables", "-N", self.CHAIN_NAME])
                logger.info(f"Created iptables chain: {self.CHAIN_NAME}")

            # Ensure INPUT and FORWARD jump to our chain for wg0 traffic
            self._ensure_jump_rule("INPUT")
            self._ensure_jump_rule("FORWARD")

        except Exception as e:
            logger.error(f"Failed to setup iptables chain: {e}")

    def _ensure_jump_rule(self, parent_chain: str):
        """Ensure parent chain jumps to ZT_ACL for wg0 traffic"""
        # Check if jump rule exists
        result = self._run(
            ["iptables", "-C", parent_chain, "-i", self.interface, "-j", self.CHAIN_NAME],
            check=False
        )

        if result.returncode != 0:
            # Add jump rule at the beginning
            self._run(["iptables", "-I", parent_chain, "1", "-i", self.interface, "-j", self.CHAIN_NAME])
            logger.info(f"Added jump rule: {parent_chain} -> {self.CHAIN_NAME}")

    def flush_rules(self):
        """Flush all rules in ZT_ACL chain"""
        try:
            self._run(["iptables", "-F", self.CHAIN_NAME])
            logger.info("Flushed ZT_ACL chain")
        except Exception as e:
            logger.error(f"Failed to flush rules: {e}")

    def apply_rules(self, rules: List[Dict[str, Any]]):
        """
        Apply ACL rules from Control Plane

        Rule format:
        {
            "src_ip": "10.0.0.0/24",      # Optional, source IP/CIDR
            "dst_ip": "10.0.0.2/32",       # Optional, destination IP/CIDR
            "protocol": "tcp",             # tcp, udp, icmp, any
            "port": 5432,                  # Optional, destination port
            "action": "allow"              # allow or deny
        }
        """
        # Flush existing rules
        self.flush_rules()

        # Sort rules by specificity (most specific first)
        sorted_rules = sorted(rules, key=lambda r: self._rule_priority(r), reverse=True)

        # Apply each rule
        for rule in sorted_rules:
            self._add_rule(rule)

        # Add default deny at the end (Zero Trust)
        self._add_default_deny()

        logger.info(f"Applied {len(rules)} ACL rules")

    def _rule_priority(self, rule: Dict[str, Any]) -> int:
        """Calculate rule priority based on specificity"""
        priority = 0

        # More specific IPs = higher priority
        if rule.get("src_ip") and "/32" in rule.get("src_ip", ""):
            priority += 100
        elif rule.get("src_ip"):
            priority += 50

        if rule.get("dst_ip") and "/32" in rule.get("dst_ip", ""):
            priority += 100
        elif rule.get("dst_ip"):
            priority += 50

        # Specific port = higher priority
        if rule.get("port"):
            priority += 25

        # Specific protocol = higher priority
        if rule.get("protocol") and rule["protocol"] not in ("any", "all"):
            priority += 10

        return priority

    def _add_rule(self, rule: Dict[str, Any]) -> bool:
        """Add a single iptables rule"""
        try:
            cmd = ["iptables", "-A", self.CHAIN_NAME]

            # Source IP
            if rule.get("src_ip"):
                cmd.extend(["-s", rule["src_ip"]])

            # Destination IP
            if rule.get("dst_ip"):
                cmd.extend(["-d", rule["dst_ip"]])

            # Protocol
            protocol = rule.get("protocol", "any").lower()
            if protocol not in ("any", "all"):
                cmd.extend(["-p", protocol])

                # Port (only for tcp/udp)
                if rule.get("port") and protocol in ("tcp", "udp"):
                    cmd.extend(["--dport", str(rule["port"])])

            # Action
            action = rule.get("action", "deny").lower()
            if action == "allow":
                cmd.extend(["-j", "ACCEPT"])
            else:
                cmd.extend(["-j", "DROP"])

            # Add comment for debugging
            description = rule.get("description", "ZT Rule")
            cmd.extend(["-m", "comment", "--comment", description[:256]])

            self._run(cmd)
            logger.debug(f"Added rule: {rule}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add rule {rule}: {e.stderr}")
            return False

    def _add_default_deny(self):
        """Add default deny rule (Zero Trust principle)"""
        try:
            # Allow established connections
            self._run([
                "iptables", "-A", self.CHAIN_NAME,
                "-m", "state", "--state", "ESTABLISHED,RELATED",
                "-j", "ACCEPT",
                "-m", "comment", "--comment", "Allow established"
            ])

            # Allow ICMP ping (optional, for troubleshooting)
            self._run([
                "iptables", "-A", self.CHAIN_NAME,
                "-p", "icmp", "--icmp-type", "echo-request",
                "-j", "ACCEPT",
                "-m", "comment", "--comment", "Allow ping"
            ])

            # Default deny
            self._run([
                "iptables", "-A", self.CHAIN_NAME,
                "-j", "DROP",
                "-m", "comment", "--comment", "ZT Default Deny"
            ])

            logger.debug("Added default deny rule")

        except Exception as e:
            logger.error(f"Failed to add default deny: {e}")

    def list_rules(self) -> str:
        """List all rules in ZT_ACL chain"""
        try:
            result = self._run(["iptables", "-L", self.CHAIN_NAME, "-n", "-v", "--line-numbers"])
            return result.stdout
        except Exception as e:
            return f"Error: {e}"

    def save_rules(self, path: str = "/etc/iptables.rules"):
        """Save rules to file for persistence"""
        try:
            result = self._run(["iptables-save"])
            with open(path, 'w') as f:
                f.write(result.stdout)
            logger.info(f"Saved iptables rules to {path}")
        except Exception as e:
            logger.error(f"Failed to save rules: {e}")

    def restore_rules(self, path: str = "/etc/iptables.rules"):
        """Restore rules from file"""
        try:
            with open(path, 'r') as f:
                rules = f.read()

            subprocess.run(
                ["iptables-restore"],
                input=rules,
                text=True,
                check=True
            )
            logger.info(f"Restored iptables rules from {path}")
        except Exception as e:
            logger.error(f"Failed to restore rules: {e}")

    def cleanup(self):
        """Remove ZT_ACL chain and all references"""
        try:
            # Remove jump rules from INPUT and FORWARD
            self._run(
                ["iptables", "-D", "INPUT", "-i", self.interface, "-j", self.CHAIN_NAME],
                check=False
            )
            self._run(
                ["iptables", "-D", "FORWARD", "-i", self.interface, "-j", self.CHAIN_NAME],
                check=False
            )

            # Flush and delete chain
            self._run(["iptables", "-F", self.CHAIN_NAME], check=False)
            self._run(["iptables", "-X", self.CHAIN_NAME], check=False)

            logger.info("Cleaned up ZT_ACL chain")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")


class NFTablesManager:
    """
    Alternative firewall manager using nftables (modern replacement for iptables)

    TODO: Implement for systems using nftables
    """

    def __init__(self, interface: str = "wg0"):
        self.interface = interface
        logger.warning("NFTables manager not yet implemented, using iptables")

    def apply_rules(self, rules: List[Dict[str, Any]]):
        """Apply rules using nftables"""
        raise NotImplementedError("Use IPTablesManager for now")
