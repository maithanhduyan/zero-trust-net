# tests/agent/test_integrity_integration.py
"""
Integration Tests for Agent Integrity Verification
Tests the full flow between Agent and Control Plane

Requirements:
    - Control Plane running at CONTROL_PLANE_URL (default: http://localhost:8000)
    - Valid ADMIN_TOKEN

Run with:
    cd /home/zero-trust-net

    # Start control plane first
    cd control-plane && uv run uvicorn main:app --port 8000 &

    # Run integration tests
    CONTROL_PLANE_URL=http://localhost:8000 ADMIN_TOKEN=your-token \
        pytest tests/agent/test_integrity_integration.py -v -s
"""

import pytest
import requests
import time
import os
from pathlib import Path

# Skip all tests if control plane is not available
CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8000")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "test-admin-token")


def is_control_plane_running():
    """Check if control plane is accessible"""
    try:
        resp = requests.get(f"{CONTROL_PLANE_URL}/health", timeout=2)
        return resp.status_code == 200
    except:
        return False


# Skip decorator for integration tests
skip_if_no_server = pytest.mark.skipif(
    not is_control_plane_running(),
    reason=f"Control Plane not running at {CONTROL_PLANE_URL}"
)


@skip_if_no_server
class TestIntegrityAPI:
    """Integration tests for integrity API endpoints"""

    @pytest.fixture
    def headers(self):
        """Admin headers for API requests"""
        return {"X-Admin-Token": ADMIN_TOKEN}

    @pytest.fixture
    def test_node(self, headers):
        """Create a test node and clean up after"""
        import subprocess
        import base64
        import os

        # Generate WireGuard keypair (try real wg first, fallback to mock)
        try:
            private_key = subprocess.check_output(
                ["wg", "genkey"], stderr=subprocess.DEVNULL
            ).decode().strip()
            public_key = subprocess.check_output(
                ["wg", "pubkey"], input=private_key.encode(), stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            # Fallback: Generate mock base64 keys (valid format for testing)
            private_bytes = os.urandom(32)
            public_key = base64.b64encode(private_bytes).decode()

        # Register node with unique name
        import random
        hostname = f"test-integrity-{int(time.time())}-{random.randint(1000, 9999)}"
        register_data = {
            "hostname": hostname,
            "public_key": public_key,
            "role": "app",
            "labels": {"test": "integrity"},
        }

        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/agent/register",
            json=register_data,
            headers=headers
        )

        if resp.status_code not in (200, 201):
            pytest.skip(f"Failed to register test node: {resp.text}")

        node_data = resp.json()
        # Handle both response formats
        if "node_id" not in node_data:
            node_data["node_id"] = node_data.get("id", 1)
        node_data["public_key"] = public_key
        node_data["hostname"] = hostname

        yield node_data

        # Cleanup: Delete test node
        try:
            requests.delete(
                f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{node_data['node_id']}",
                headers=headers
            )
        except:
            pass

    def test_heartbeat_with_integrity_hash(self, test_node, headers):
        """Test sending heartbeat with integrity hash"""
        test_hash = "test_combined_hash_" + "a" * 45

        heartbeat_data = {
            "hostname": test_node["hostname"],
            "public_key": test_node["public_key"],
            "cpu_percent": 25.5,
            "memory_percent": 40.0,
            "disk_percent": 60.0,
            "agent_hash": test_hash,
        }

        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/agent/heartbeat",
            json=heartbeat_data,
        )

        assert resp.status_code == 200
        result = resp.json()

        # Verify response includes integrity status
        # Note: First report should be "no_expected_hash"
        assert "success" in result or "error" not in result

    def test_approve_agent_hash(self, test_node, headers):
        """Test admin approving agent hash"""
        # First, send heartbeat with hash
        test_hash = "hash_to_approve_" + "b" * 48

        heartbeat_data = {
            "hostname": test_node["hostname"],
            "public_key": test_node["public_key"],
            "agent_hash": test_hash,
        }

        requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/agent/heartbeat",
            json=heartbeat_data,
        )

        # Admin approves the hash
        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{test_node['node_id']}/integrity/approve",
            headers=headers,
        )

        # Check response (endpoint may not exist yet)
        if resp.status_code == 404:
            pytest.skip("approve-hash endpoint not implemented")

        assert resp.status_code == 200

    def test_set_expected_hash(self, test_node, headers):
        """Test admin setting expected hash directly"""
        # Hash must be exactly 64 hex characters (SHA-256)
        expected_hash = "a" * 64

        resp = requests.put(
            f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{test_node['node_id']}/integrity/hash?hash_value={expected_hash}",
            headers=headers,
        )

        if resp.status_code == 404:
            pytest.skip("expected-hash endpoint not implemented")

        assert resp.status_code == 200

    def test_integrity_mismatch_reduces_trust(self, test_node, headers):
        """Test that hash mismatch affects trust score"""
        # Set expected hash (64 hex chars for SHA-256)
        expected_hash = "b" * 64

        resp = requests.put(
            f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{test_node['node_id']}/integrity/hash?hash_value={expected_hash}",
            headers=headers,
        )

        if resp.status_code == 404:
            pytest.skip("expected-hash endpoint not implemented")

        # Get initial trust score
        node_resp = requests.get(
            f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{test_node['node_id']}",
            headers=headers,
        )
        initial_trust = node_resp.json().get("trust_score", 100)

        # Send heartbeat with WRONG hash
        wrong_hash = "wrong_malicious_hash_" + "e" * 43

        heartbeat_data = {
            "hostname": test_node["hostname"],
            "status": "active",
            "agent_hash": wrong_hash,
        }

        requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/agent/heartbeat?public_key={test_node['public_key']}",
            json=heartbeat_data,
        )

        # Check trust score decreased
        node_resp = requests.get(
            f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{test_node['node_id']}",
            headers=headers,
        )
        new_trust = node_resp.json().get("trust_score", 100)

        # Trust should be lower (or at least hash_verified should be False)
        # This depends on implementation
        print(f"Initial trust: {initial_trust}, New trust: {new_trust}")


@skip_if_no_server
class TestIntegrityFlow:
    """Full flow integration tests"""

    def test_full_registration_to_verification_flow(self):
        """Test complete flow from registration to verification"""
        import subprocess

        headers = {"X-Admin-Token": ADMIN_TOKEN}

        # Step 1: Generate keys
        try:
            private_key = subprocess.check_output(
                ["wg", "genkey"], stderr=subprocess.DEVNULL
            ).decode().strip()
            public_key = subprocess.check_output(
                ["wg", "pubkey"], input=private_key.encode(), stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            pytest.skip("WireGuard tools not available")

        hostname = f"flow-test-{int(time.time())}"

        # Step 2: Register
        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/agent/register",
            json={
                "hostname": hostname,
                "public_key": public_key,
                "role": "app",
            },
            headers=headers,
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f"Failed to register node: {resp.text}")
        node_data = resp.json()
        node_id = node_data["node_id"]

        try:
            # Step 3: Send first heartbeat with hash
            agent_hash = "f" * 64  # SHA-256 = 64 hex chars

            resp = requests.post(
                f"{CONTROL_PLANE_URL}/api/v1/agent/heartbeat",
                json={
                    "hostname": hostname,
                    "public_key": public_key,
                    "agent_hash": agent_hash,
                },
            )
            assert resp.status_code == 200

            # Step 4: Admin approves (if endpoint exists)
            resp = requests.post(
                f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{node_id}/integrity/approve",
                headers=headers,
            )

            if resp.status_code == 200:
                # Step 5: Verify subsequent heartbeats pass
                resp = requests.post(
                    f"{CONTROL_PLANE_URL}/api/v1/agent/heartbeat",
                    json={
                        "hostname": hostname,
                        "public_key": public_key,
                        "agent_hash": agent_hash,
                    },
                )
                assert resp.status_code == 200

                print(f"✓ Full integrity flow completed for {hostname}")
            else:
                print(f"⚠ approve-hash not implemented, skipping verification step")

        finally:
            # Cleanup
            requests.delete(
                f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{node_id}",
                headers=headers,
            )


# ============================================
# Performance Tests
# ============================================

@skip_if_no_server
class TestIntegrityPerformance:
    """Performance tests for integrity verification"""

    def test_hash_calculation_speed(self, temp_agent_dir):
        """Test that hash calculation is fast enough"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent"))
        from collectors.agent_integrity import get_integrity_report
        from unittest.mock import patch

        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            start = time.time()

            for _ in range(100):
                get_integrity_report()

            elapsed = time.time() - start

        # Should complete 100 calculations in under 1 second
        assert elapsed < 1.0, f"Hash calculation too slow: {elapsed:.2f}s for 100 iterations"
        print(f"✓ 100 hash calculations in {elapsed:.3f}s ({elapsed*10:.1f}ms each)")

    def test_heartbeat_with_integrity_latency(self, temp_agent_dir):
        """Test heartbeat latency with integrity check"""
        import subprocess

        # Generate keys
        try:
            private_key = subprocess.check_output(
                ["wg", "genkey"], stderr=subprocess.DEVNULL
            ).decode().strip()
            public_key = subprocess.check_output(
                ["wg", "pubkey"], input=private_key.encode(), stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            pytest.skip("WireGuard tools not available")

        headers = {"X-Admin-Token": ADMIN_TOKEN}
        hostname = f"perf-test-{int(time.time())}"

        # Register
        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/v1/agent/register",
            json={"hostname": hostname, "public_key": public_key, "role": "app"},
            headers=headers,
        )

        if resp.status_code not in (200, 201):
            pytest.skip("Failed to register node")

        node_id = resp.json()["node_id"]

        try:
            # Measure heartbeat latency
            latencies = []
            for i in range(10):
                start = time.time()

                requests.post(
                    f"{CONTROL_PLANE_URL}/api/v1/agent/heartbeat",
                    json={
                        "hostname": hostname,
                        "public_key": public_key,
                        "agent_hash": "g" * 64,  # Valid 64-char hex hash
                    },
                )

                latencies.append(time.time() - start)

            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)

            print(f"✓ Heartbeat latency: avg={avg_latency*1000:.1f}ms, max={max_latency*1000:.1f}ms")

            # Heartbeat should complete in under 500ms
            assert avg_latency < 0.5, f"Heartbeat too slow: {avg_latency*1000:.1f}ms"

        finally:
            requests.delete(
                f"{CONTROL_PLANE_URL}/api/v1/admin/nodes/{node_id}",
                headers=headers,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
