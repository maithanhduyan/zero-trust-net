# tests/agent/conftest.py
"""
Pytest fixtures for Agent tests
Shared configuration and mock objects
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime

# Add paths for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))
sys.path.insert(0, str(PROJECT_ROOT / "control-plane"))


# ============================================
# Fixtures for Agent Integrity Tests
# ============================================

@pytest.fixture
def temp_agent_dir():
    """Create a temporary directory with mock agent files"""
    temp_dir = tempfile.mkdtemp(prefix="zt-agent-test-")

    # Create mock agent files
    files = {
        "agent.py": "# Agent main file\nprint('Hello')\n",
        "client.py": "# HTTP client\nimport requests\n",
        "websocket_client.py": "# WebSocket client\nimport asyncio\n",
        "collectors/__init__.py": "",
        "collectors/agent_integrity.py": "# Integrity module\nimport hashlib\n",
        "collectors/host_info.py": "# Host info collector\nimport platform\n",
        "collectors/security_events.py": "# Security events\nimport logging\n",
        "collectors/network_stats.py": "# Network stats\nimport socket\n",
        "firewall/__init__.py": "",
        "firewall/iptables.py": "# IPTables manager\nimport subprocess\n",
        "wireguard/__init__.py": "",
        "wireguard/manager.py": "# WireGuard manager\nimport os\n",
        "wireguard/config_builder.py": "# Config builder\nimport configparser\n",
    }

    for filepath, content in files.items():
        full_path = Path(temp_dir) / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_node():
    """Create a mock Node object for testing"""
    node = Mock()
    node.id = 1
    node.hostname = "test-node-01"
    node.public_key = "test-public-key-abc123"
    node.status = "active"
    node.role = "app"
    node.trust_score = 85.0
    node.agent_hash = None
    node.last_reported_hash = None
    node.hash_verified = False
    node.hash_mismatch_count = 0
    node.agent_version = "1.0.0"
    node.real_ip = "192.168.1.100"
    return node


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = Mock()
    db.commit = Mock()
    db.add = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def sample_file_hashes():
    """Sample file hashes for testing"""
    return {
        "agent.py": "a" * 64,
        "client.py": "b" * 64,
        "websocket_client.py": "c" * 64,
        "collectors/agent_integrity.py": "d" * 64,
        "collectors/host_info.py": "e" * 64,
    }


@pytest.fixture
def control_plane_url():
    """Control plane URL for integration tests"""
    return os.environ.get("CONTROL_PLANE_URL", "http://localhost:8000")


@pytest.fixture
def admin_token():
    """Admin token for API tests"""
    return os.environ.get("ADMIN_TOKEN", "test-admin-token")


# ============================================
# Fixtures for Integration Tests
# ============================================

@pytest.fixture
def test_node_config():
    """Configuration for test node registration"""
    return {
        "hostname": f"pytest-node-{datetime.now().strftime('%H%M%S')}",
        "role": "app",
        "labels": {"env": "test", "purpose": "pytest"},
    }


@pytest.fixture
def wireguard_keypair():
    """Generate WireGuard keypair for testing"""
    try:
        import subprocess
        private_key = subprocess.check_output(
            ["wg", "genkey"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        public_key = subprocess.check_output(
            ["wg", "pubkey"],
            input=private_key.encode(),
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return {"private_key": private_key, "public_key": public_key}
    except Exception:
        # Fallback for systems without wg command
        return {
            "private_key": "cFakePrivateKeyForTesting123456789012345=",
            "public_key": "pFakePublicKeyForTesting1234567890123456=",
        }
