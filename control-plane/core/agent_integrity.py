# control-plane/core/agent_integrity.py
"""
Agent Integrity Verification Service
Verifies that agent software hasn't been tampered with

Security Model:
1. Admin sets expected agent_hash for each node (or globally)
2. Agent reports its hash on every heartbeat
3. Server compares and updates trust score if mismatch
4. Multiple mismatches trigger suspension/revocation

This prevents:
- Malicious agents sending fake data
- Man-in-the-middle modifying agent code
- Compromised nodes pretending to be healthy
"""

import logging
from typing import Optional, Tuple, Dict, List
from datetime import datetime
from sqlalchemy.orm import Session

from database.models import Node, AuditLog

logger = logging.getLogger(__name__)


# Tolerance: how many consecutive mismatches before action
HASH_MISMATCH_WARNING_THRESHOLD = 1   # Log warning
HASH_MISMATCH_SUSPEND_THRESHOLD = 3   # Suspend node
HASH_MISMATCH_REVOKE_THRESHOLD = 5    # Revoke node

# Trust penalty for hash mismatch
HASH_MISMATCH_TRUST_PENALTY = 0.3     # Reduce trust by 30%


class AgentIntegrityService:
    """
    Service for verifying agent software integrity
    """

    def __init__(self):
        # Global expected hash (used if node-specific not set)
        self.global_expected_hash: Optional[str] = None

        # Known good hashes by version
        self.known_good_hashes: Dict[str, str] = {}

    def set_global_expected_hash(self, hash_value: str):
        """Set the global expected hash for all agents"""
        self.global_expected_hash = hash_value
        logger.info(f"Global agent hash set: {hash_value[:16]}...")

    def register_known_hash(self, version: str, hash_value: str):
        """Register a known good hash for a specific agent version"""
        self.known_good_hashes[version] = hash_value
        logger.info(f"Registered hash for agent v{version}: {hash_value[:16]}...")

    def get_expected_hash(self, node: Node) -> Optional[str]:
        """
        Get the expected hash for a node
        Priority: node-specific > version-specific > global
        """
        # 1. Node-specific hash (set by admin)
        if node.agent_hash:
            return node.agent_hash

        # 2. Version-specific hash
        if node.agent_version and node.agent_version in self.known_good_hashes:
            return self.known_good_hashes[node.agent_version]

        # 3. Global hash
        return self.global_expected_hash

    def verify_integrity(
        self,
        db: Session,
        node: Node,
        reported_hash: str,
        file_hashes: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Verify agent integrity based on reported hash

        Args:
            db: Database session
            node: Node object
            reported_hash: Hash reported by agent
            file_hashes: Optional per-file hashes for detailed check

        Returns:
            Tuple of (is_valid, action_taken)
            action_taken: "verified", "first_report", "mismatch_warning",
                         "suspended", "revoked", "no_expected_hash"
        """
        expected_hash = self.get_expected_hash(node)

        # Update last reported hash
        node.last_reported_hash = reported_hash

        # Case 1: No expected hash configured
        if not expected_hash:
            # First time seeing this agent - record hash for admin review
            if not node.agent_hash and not node.last_reported_hash:
                logger.info(
                    f"First hash report from {node.hostname}: {reported_hash[:16]}... "
                    "(awaiting admin approval)"
                )
                self._log_audit(db, node, "INTEGRITY_FIRST_REPORT", reported_hash)

            node.hash_verified = False
            db.commit()
            return True, "no_expected_hash"

        # Case 2: Hash matches
        if reported_hash == expected_hash:
            if not node.hash_verified or node.hash_mismatch_count > 0:
                logger.info(f"Agent integrity verified for {node.hostname}")
                self._log_audit(db, node, "INTEGRITY_VERIFIED", reported_hash)

            node.hash_verified = True
            node.hash_mismatch_count = 0
            db.commit()
            return True, "verified"

        # Case 3: Hash mismatch!
        node.hash_verified = False
        node.hash_mismatch_count += 1

        mismatch_count = node.hash_mismatch_count

        logger.warning(
            f"AGENT INTEGRITY MISMATCH for {node.hostname}! "
            f"Expected: {expected_hash[:16]}..., Got: {reported_hash[:16]}... "
            f"(count: {mismatch_count})"
        )

        self._log_audit(
            db, node, "INTEGRITY_MISMATCH",
            f"expected={expected_hash[:32]}, got={reported_hash[:32]}, count={mismatch_count}",
            severity="warning" if mismatch_count < HASH_MISMATCH_SUSPEND_THRESHOLD else "critical"
        )

        action = "mismatch_warning"

        # Take action based on mismatch count
        if mismatch_count >= HASH_MISMATCH_REVOKE_THRESHOLD:
            node.status = "revoked"
            action = "revoked"
            logger.critical(
                f"Node {node.hostname} REVOKED due to persistent integrity mismatch"
            )
        elif mismatch_count >= HASH_MISMATCH_SUSPEND_THRESHOLD:
            node.status = "suspended"
            action = "suspended"
            logger.error(
                f"Node {node.hostname} SUSPENDED due to integrity mismatch"
            )

        db.commit()
        return False, action

    def get_trust_penalty(self, node: Node) -> float:
        """
        Get trust penalty for integrity issues
        Returns a value to subtract from trust score
        """
        if node.hash_verified:
            return 0.0

        if node.hash_mismatch_count == 0:
            return 0.0

        # Progressive penalty based on mismatch count
        penalty = min(
            HASH_MISMATCH_TRUST_PENALTY * node.hash_mismatch_count,
            0.9  # Max 90% penalty
        )

        return penalty

    def approve_reported_hash(self, db: Session, node: Node) -> bool:
        """
        Admin action: Approve the current reported hash as the expected hash
        Used for initial setup or after legitimate agent update
        """
        if not node.last_reported_hash:
            logger.warning(f"No reported hash to approve for {node.hostname}")
            return False

        node.agent_hash = node.last_reported_hash
        node.hash_verified = True
        node.hash_mismatch_count = 0

        self._log_audit(
            db, node, "INTEGRITY_APPROVED",
            f"hash={node.agent_hash[:32]}...",
            severity="info"
        )

        db.commit()
        logger.info(f"Approved agent hash for {node.hostname}: {node.agent_hash[:16]}...")
        return True

    def _log_audit(
        self,
        db: Session,
        node: Node,
        action: str,
        details: str,
        severity: str = "info"
    ):
        """Log integrity event to audit log"""
        try:
            audit = AuditLog(
                action=action,
                actor_type="system",
                actor_id="integrity_service",
                target_type="node",
                target_id=str(node.id),
                details=details,
                ip_address=node.real_ip,
                created_at=datetime.utcnow()
            )
            db.add(audit)
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")


# Singleton instance
integrity_service = AgentIntegrityService()
