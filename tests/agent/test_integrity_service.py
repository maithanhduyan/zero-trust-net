# tests/agent/test_integrity_service.py
"""
Unit Tests for Control Plane Agent Integrity Service
Tests the server-side verification and action logic

Run with:
    cd /home/zero-trust-net
    pytest tests/agent/test_integrity_service.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "control-plane"))

from core.agent_integrity import (
    AgentIntegrityService,
    HASH_MISMATCH_WARNING_THRESHOLD,
    HASH_MISMATCH_SUSPEND_THRESHOLD,
    HASH_MISMATCH_REVOKE_THRESHOLD,
    HASH_MISMATCH_TRUST_PENALTY,
)


class TestAgentIntegrityService:
    """Tests for AgentIntegrityService class"""

    @pytest.fixture
    def service(self):
        """Create fresh service instance for each test"""
        return AgentIntegrityService()

    @pytest.fixture
    def mock_node(self):
        """Create mock node"""
        node = Mock()
        node.id = 1
        node.hostname = "test-node"
        node.agent_hash = None
        node.last_reported_hash = None
        node.hash_verified = False
        node.hash_mismatch_count = 0
        node.agent_version = "1.0.0"
        node.status = "active"
        node.real_ip = "10.0.0.5"
        return node

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        db.commit = Mock()
        db.add = Mock()
        return db


class TestSetGlobalExpectedHash(TestAgentIntegrityService):
    """Tests for set_global_expected_hash"""

    def test_sets_global_hash(self, service):
        """Test setting global hash"""
        test_hash = "a" * 64

        service.set_global_expected_hash(test_hash)

        assert service.global_expected_hash == test_hash

    def test_overwrites_previous_hash(self, service):
        """Test that new hash replaces old"""
        service.set_global_expected_hash("a" * 64)
        service.set_global_expected_hash("b" * 64)

        assert service.global_expected_hash == "b" * 64


class TestRegisterKnownHash(TestAgentIntegrityService):
    """Tests for register_known_hash"""

    def test_registers_version_hash(self, service):
        """Test registering hash for specific version"""
        service.register_known_hash("1.0.0", "a" * 64)
        service.register_known_hash("1.1.0", "b" * 64)

        assert service.known_good_hashes["1.0.0"] == "a" * 64
        assert service.known_good_hashes["1.1.0"] == "b" * 64


class TestGetExpectedHash(TestAgentIntegrityService):
    """Tests for get_expected_hash"""

    def test_priority_node_specific(self, service, mock_node):
        """Test that node-specific hash has highest priority"""
        mock_node.agent_hash = "node_specific_" + "a" * 50
        service.global_expected_hash = "global_" + "b" * 57

        result = service.get_expected_hash(mock_node)

        assert result == mock_node.agent_hash

    def test_priority_version_specific(self, service, mock_node):
        """Test version-specific hash when no node-specific"""
        mock_node.agent_hash = None
        mock_node.agent_version = "1.0.0"
        service.register_known_hash("1.0.0", "version_" + "c" * 56)
        service.global_expected_hash = "global_" + "d" * 57

        result = service.get_expected_hash(mock_node)

        assert result == "version_" + "c" * 56

    def test_priority_global(self, service, mock_node):
        """Test global hash as fallback"""
        mock_node.agent_hash = None
        mock_node.agent_version = None
        service.global_expected_hash = "global_" + "e" * 57

        result = service.get_expected_hash(mock_node)

        assert result == "global_" + "e" * 57

    def test_returns_none_when_no_hash(self, service, mock_node):
        """Test returns None when no hash configured"""
        mock_node.agent_hash = None
        mock_node.agent_version = None

        result = service.get_expected_hash(mock_node)

        assert result is None


class TestVerifyIntegrity(TestAgentIntegrityService):
    """Tests for verify_integrity method"""

    def test_no_expected_hash_first_report(self, service, mock_node, mock_db):
        """Test first report when no expected hash configured"""
        mock_node.agent_hash = None
        mock_node.last_reported_hash = None

        is_valid, action = service.verify_integrity(
            mock_db, mock_node, "reported_" + "a" * 55
        )

        assert is_valid is True
        assert action == "no_expected_hash"
        mock_db.commit.assert_called()

    def test_hash_matches(self, service, mock_node, mock_db):
        """Test when reported hash matches expected"""
        expected = "matching_hash_" + "b" * 50
        mock_node.agent_hash = expected

        is_valid, action = service.verify_integrity(mock_db, mock_node, expected)

        assert is_valid is True
        assert action == "verified"
        assert mock_node.hash_verified is True
        assert mock_node.hash_mismatch_count == 0

    def test_hash_mismatch_warning(self, service, mock_node, mock_db):
        """Test first mismatch triggers warning"""
        mock_node.agent_hash = "expected_" + "c" * 55
        mock_node.hash_mismatch_count = 0

        is_valid, action = service.verify_integrity(
            mock_db, mock_node, "wrong_hash_" + "d" * 53
        )

        assert is_valid is False
        assert action == "mismatch_warning"
        assert mock_node.hash_mismatch_count == 1
        assert mock_node.hash_verified is False

    def test_hash_mismatch_suspends_after_threshold(self, service, mock_node, mock_db):
        """Test suspension after multiple mismatches"""
        mock_node.agent_hash = "expected_" + "e" * 55
        mock_node.hash_mismatch_count = HASH_MISMATCH_SUSPEND_THRESHOLD - 1

        is_valid, action = service.verify_integrity(
            mock_db, mock_node, "wrong_hash_" + "f" * 53
        )

        assert is_valid is False
        assert action == "suspended"
        assert mock_node.status == "suspended"

    def test_hash_mismatch_revokes_after_threshold(self, service, mock_node, mock_db):
        """Test revocation after many mismatches"""
        mock_node.agent_hash = "expected_" + "g" * 55
        mock_node.hash_mismatch_count = HASH_MISMATCH_REVOKE_THRESHOLD - 1

        is_valid, action = service.verify_integrity(
            mock_db, mock_node, "wrong_hash_" + "h" * 53
        )

        assert is_valid is False
        assert action == "revoked"
        assert mock_node.status == "revoked"

    def test_recovery_after_correct_hash(self, service, mock_node, mock_db):
        """Test that node recovers when correct hash is reported"""
        expected = "correct_hash_" + "i" * 51
        mock_node.agent_hash = expected
        mock_node.hash_mismatch_count = 2
        mock_node.hash_verified = False

        is_valid, action = service.verify_integrity(mock_db, mock_node, expected)

        assert is_valid is True
        assert action == "verified"
        assert mock_node.hash_verified is True
        assert mock_node.hash_mismatch_count == 0


class TestGetTrustPenalty(TestAgentIntegrityService):
    """Tests for get_trust_penalty method"""

    def test_no_penalty_when_verified(self, service, mock_node):
        """Test no penalty for verified nodes"""
        mock_node.hash_verified = True
        mock_node.hash_mismatch_count = 0

        penalty = service.get_trust_penalty(mock_node)

        assert penalty == 0.0

    def test_no_penalty_when_no_mismatch(self, service, mock_node):
        """Test no penalty when no mismatches"""
        mock_node.hash_verified = False
        mock_node.hash_mismatch_count = 0

        penalty = service.get_trust_penalty(mock_node)

        assert penalty == 0.0

    def test_progressive_penalty(self, service, mock_node):
        """Test penalty increases with mismatch count"""
        mock_node.hash_verified = False

        mock_node.hash_mismatch_count = 1
        penalty1 = service.get_trust_penalty(mock_node)

        mock_node.hash_mismatch_count = 2
        penalty2 = service.get_trust_penalty(mock_node)

        assert penalty2 > penalty1

    def test_max_penalty_capped(self, service, mock_node):
        """Test penalty is capped at 90%"""
        mock_node.hash_verified = False
        mock_node.hash_mismatch_count = 100  # Many mismatches

        penalty = service.get_trust_penalty(mock_node)

        assert penalty <= 0.9


class TestApproveReportedHash(TestAgentIntegrityService):
    """Tests for approve_reported_hash method"""

    def test_approve_sets_hash(self, service, mock_node, mock_db):
        """Test approving sets expected hash from reported"""
        mock_node.last_reported_hash = "reported_" + "j" * 55
        mock_node.agent_hash = None

        result = service.approve_reported_hash(mock_db, mock_node)

        assert result is True
        assert mock_node.agent_hash == mock_node.last_reported_hash
        assert mock_node.hash_verified is True
        assert mock_node.hash_mismatch_count == 0

    def test_approve_fails_without_reported(self, service, mock_node, mock_db):
        """Test approval fails if no hash reported"""
        mock_node.last_reported_hash = None

        result = service.approve_reported_hash(mock_db, mock_node)

        assert result is False


# ============================================
# Scenario Tests
# ============================================

class TestIntegrityScenarios:
    """End-to-end scenario tests"""

    @pytest.fixture
    def service(self):
        return AgentIntegrityService()

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.commit = Mock()
        db.add = Mock()
        return db

    def test_scenario_new_agent_registration(self, service, mock_db):
        """Scenario: New agent registers, admin approves"""
        node = Mock()
        node.id = 1
        node.hostname = "new-agent"
        node.agent_hash = None
        node.last_reported_hash = None
        node.hash_verified = False
        node.hash_mismatch_count = 0
        node.agent_version = "1.0.0"
        node.status = "active"
        node.real_ip = "10.0.0.100"

        # Step 1: Agent reports hash (no expected configured)
        is_valid, action = service.verify_integrity(
            mock_db, node, "new_agent_hash_" + "k" * 50
        )
        assert action == "no_expected_hash"

        # Step 2: Admin approves
        node.last_reported_hash = "new_agent_hash_" + "k" * 50
        result = service.approve_reported_hash(mock_db, node)
        assert result is True

        # Step 3: Subsequent verification passes
        is_valid, action = service.verify_integrity(
            mock_db, node, node.agent_hash
        )
        assert is_valid is True
        assert action == "verified"

    def test_scenario_agent_tampered(self, service, mock_db):
        """Scenario: Agent is compromised and tampered with"""
        node = Mock()
        node.id = 2
        node.hostname = "compromised-agent"
        node.agent_hash = "legitimate_hash_" + "l" * 48
        node.last_reported_hash = None
        node.hash_verified = True
        node.hash_mismatch_count = 0
        node.agent_version = "1.0.0"
        node.status = "active"
        node.real_ip = "10.0.0.101"

        tampered_hash = "malicious_hash_" + "m" * 49

        # Attacker modifies agent - mismatch 1
        is_valid, action = service.verify_integrity(mock_db, node, tampered_hash)
        assert is_valid is False
        assert action == "mismatch_warning"

        # Continues to report bad hash - mismatch 2
        is_valid, action = service.verify_integrity(mock_db, node, tampered_hash)
        assert action == "mismatch_warning"

        # Mismatch 3 - suspended
        is_valid, action = service.verify_integrity(mock_db, node, tampered_hash)
        assert action == "suspended"
        assert node.status == "suspended"

    def test_scenario_agent_update(self, service, mock_db):
        """Scenario: Legitimate agent update changes hash"""
        node = Mock()
        node.id = 3
        node.hostname = "updating-agent"
        node.agent_hash = "old_version_hash_" + "n" * 47
        node.last_reported_hash = None
        node.hash_verified = True
        node.hash_mismatch_count = 0
        node.agent_version = "1.0.0"
        node.status = "active"
        node.real_ip = "10.0.0.102"

        new_hash = "new_version_hash_" + "o" * 47

        # Update causes mismatch
        is_valid, action = service.verify_integrity(mock_db, node, new_hash)
        assert is_valid is False

        # Admin registers new version hash before suspension
        service.register_known_hash("1.1.0", new_hash)
        node.agent_version = "1.1.0"
        node.agent_hash = None  # Clear node-specific to use version hash
        node.hash_mismatch_count = 0

        # Now verification passes
        is_valid, action = service.verify_integrity(mock_db, node, new_hash)
        assert is_valid is True
        assert action == "verified"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
