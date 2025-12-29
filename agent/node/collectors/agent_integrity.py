# agent/collectors/agent_integrity.py
"""
Agent Integrity Verification
Calculates cryptographic hashes of agent files to prove integrity to Control Plane
"""

import hashlib
import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger('zt-agent.integrity')

# Files that should be verified for integrity
CRITICAL_FILES = [
    "agent.py",
    "client.py",
    "websocket_client.py",
    "collectors/agent_integrity.py",
    "collectors/host_info.py",
    "collectors/security_events.py",
    "collectors/network_stats.py",
    "firewall/iptables.py",
    "wireguard/manager.py",
    "wireguard/config_builder.py",
]


def get_agent_base_path() -> Path:
    """Get the base path of the agent installation"""
    # Try common installation paths
    paths = [
        Path("/opt/zt-agent"),
        Path("/usr/local/lib/zt-agent"),
        Path(__file__).parent.parent,  # Development path
    ]

    for path in paths:
        if path.exists() and (path / "agent.py").exists():
            return path

    # Fallback to script directory
    return Path(__file__).parent.parent


def calculate_file_hash(filepath: Path) -> Optional[str]:
    """
    Calculate SHA-256 hash of a file
    Returns None if file doesn't exist or can't be read
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to hash {filepath}: {e}")
        return None


def calculate_agent_integrity() -> Dict[str, str]:
    """
    Calculate hashes for all critical agent files

    Returns:
        Dictionary mapping relative file path to SHA-256 hash
    """
    base_path = get_agent_base_path()
    hashes = {}

    for relative_path in CRITICAL_FILES:
        full_path = base_path / relative_path
        file_hash = calculate_file_hash(full_path)
        if file_hash:
            hashes[relative_path] = file_hash

    return hashes


def calculate_combined_hash(file_hashes: Dict[str, str]) -> str:
    """
    Calculate a combined hash from all file hashes
    This provides a single value to compare for quick integrity check
    """
    # Sort keys for deterministic ordering
    sorted_items = sorted(file_hashes.items())
    combined = json.dumps(sorted_items, sort_keys=True)
    return hashlib.sha256(combined.encode()).hexdigest()


def get_integrity_report() -> Dict:
    """
    Generate a complete integrity report for the agent

    Returns:
        {
            "combined_hash": "sha256...",  # Quick check
            "file_hashes": {...},          # Detailed per-file hashes
            "agent_path": "/opt/zt-agent", # Installation path
            "missing_files": [...]         # Files that couldn't be hashed
        }
    """
    base_path = get_agent_base_path()
    file_hashes = calculate_agent_integrity()

    # Find missing files
    missing = []
    for relative_path in CRITICAL_FILES:
        if relative_path not in file_hashes:
            missing.append(relative_path)

    return {
        "combined_hash": calculate_combined_hash(file_hashes),
        "file_hashes": file_hashes,
        "agent_path": str(base_path),
        "file_count": len(file_hashes),
        "missing_files": missing if missing else None
    }


def verify_against_expected(expected_hash: str) -> bool:
    """
    Verify current agent integrity against expected combined hash
    Used for self-check on agent startup
    """
    report = get_integrity_report()
    return report["combined_hash"] == expected_hash


# For command-line testing
if __name__ == "__main__":
    import sys

    report = get_integrity_report()

    print(f"Agent Path: {report['agent_path']}")
    print(f"Combined Hash: {report['combined_hash']}")
    print(f"Files Verified: {report['file_count']}")

    if report['missing_files']:
        print(f"Missing Files: {report['missing_files']}")

    print("\nPer-file hashes:")
    for path, hash_val in sorted(report['file_hashes'].items()):
        print(f"  {path}: {hash_val[:16]}...")
