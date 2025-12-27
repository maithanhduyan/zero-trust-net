# control-plane/core/domain_events.py
"""
Domain Events - Business events for Zero Trust Network

These events represent meaningful things that happened in the system.
Each event is immutable and contains all relevant context.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


# =============================================================================
# Event Types (Constants)
# =============================================================================

class EventTypes:
    """All domain event type constants"""

    # Node lifecycle events
    NODE_REGISTERED = "NodeRegistered"
    NODE_APPROVED = "NodeApproved"
    NODE_ACTIVATED = "NodeActivated"
    NODE_SUSPENDED = "NodeSuspended"
    NODE_REVOKED = "NodeRevoked"
    NODE_HEARTBEAT = "NodeHeartbeat"
    NODE_OFFLINE = "NodeOffline"
    NODE_CONFIG_SYNCED = "NodeConfigSynced"

    # IP Management events
    IP_ALLOCATED = "IPAllocated"
    IP_RELEASED = "IPReleased"
    IP_POOL_LOW = "IPPoolLow"
    IP_POOL_EXHAUSTED = "IPPoolExhausted"

    # Client device events
    CLIENT_DEVICE_CREATED = "ClientDeviceCreated"
    CLIENT_DEVICE_ACTIVATED = "ClientDeviceActivated"
    CLIENT_DEVICE_SUSPENDED = "ClientDeviceSuspended"
    CLIENT_DEVICE_REVOKED = "ClientDeviceRevoked"
    CLIENT_DEVICE_EXPIRED = "ClientDeviceExpired"
    CLIENT_CONFIG_DOWNLOADED = "ClientConfigDownloaded"

    # Policy events
    POLICY_CREATED = "PolicyCreated"
    POLICY_UPDATED = "PolicyUpdated"
    POLICY_DELETED = "PolicyDeleted"
    POLICY_APPLIED = "PolicyApplied"

    # Trust events
    TRUST_SCORE_CHANGED = "TrustScoreChanged"
    TRUST_THRESHOLD_BREACH = "TrustThresholdBreach"

    # Security events
    SECURITY_ALERT = "SecurityAlert"
    UNAUTHORIZED_ACCESS = "UnauthorizedAccess"
    AUTHENTICATION_FAILED = "AuthenticationFailed"

    # User events
    USER_CREATED = "UserCreated"
    USER_UPDATED = "UserUpdated"
    USER_SUSPENDED = "UserSuspended"
    USER_DELETED = "UserDeleted"

    # Group events
    GROUP_CREATED = "GroupCreated"
    GROUP_UPDATED = "GroupUpdated"
    GROUP_DELETED = "GroupDeleted"
    USER_ADDED_TO_GROUP = "UserAddedToGroup"
    USER_REMOVED_FROM_GROUP = "UserRemovedFromGroup"

    # Configuration events
    CONFIG_VERSION_INCREMENTED = "ConfigVersionIncremented"
    WIREGUARD_PEER_ADDED = "WireGuardPeerAdded"
    WIREGUARD_PEER_REMOVED = "WireGuardPeerRemoved"
    WIREGUARD_CONFIG_UPDATED = "WireGuardConfigUpdated"


# =============================================================================
# Event Payload Builders
# =============================================================================

def node_registered_payload(
    node_id: int,
    hostname: str,
    overlay_ip: str,
    public_key: str,
    role: str,
    external_ip: Optional[str] = None
) -> Dict[str, Any]:
    """Build payload for NodeRegistered event"""
    return {
        "node_id": node_id,
        "hostname": hostname,
        "overlay_ip": overlay_ip,
        "public_key": public_key,
        "role": role,
        "external_ip": external_ip,
    }


def node_status_changed_payload(
    node_id: int,
    hostname: str,
    old_status: str,
    new_status: str,
    reason: Optional[str] = None,
    changed_by: Optional[str] = None
) -> Dict[str, Any]:
    """Build payload for node status change events"""
    return {
        "node_id": node_id,
        "hostname": hostname,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
        "changed_by": changed_by,
    }


def ip_allocated_payload(
    ip_address: str,
    allocation_type: str,  # "node" or "client"
    entity_id: int,
    entity_name: str
) -> Dict[str, Any]:
    """Build payload for IPAllocated event"""
    return {
        "ip_address": ip_address,
        "allocation_type": allocation_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
    }


def client_device_created_payload(
    device_id: int,
    device_name: str,
    device_type: str,
    user_id: Optional[str],
    overlay_ip: str,
    tunnel_mode: str,
    expires_at: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build payload for ClientDeviceCreated event"""
    return {
        "device_id": device_id,
        "device_name": device_name,
        "device_type": device_type,
        "user_id": user_id,
        "overlay_ip": overlay_ip,
        "tunnel_mode": tunnel_mode,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


def client_device_status_changed_payload(
    device_id: int,
    device_name: str,
    old_status: str,
    new_status: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Build payload for client device status change events"""
    return {
        "device_id": device_id,
        "device_name": device_name,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
    }


def policy_changed_payload(
    policy_id: int,
    policy_name: str,
    action: str,  # "created", "updated", "deleted"
    changes: Optional[Dict[str, Any]] = None,
    affected_nodes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build payload for policy change events"""
    return {
        "policy_id": policy_id,
        "policy_name": policy_name,
        "action": action,
        "changes": changes,
        "affected_nodes": affected_nodes or [],
    }


def trust_score_changed_payload(
    node_id: int,
    hostname: str,
    old_score: float,
    new_score: float,
    factors: Dict[str, float]
) -> Dict[str, Any]:
    """Build payload for TrustScoreChanged event"""
    return {
        "node_id": node_id,
        "hostname": hostname,
        "old_score": old_score,
        "new_score": new_score,
        "factors": factors,
        "delta": new_score - old_score,
    }


def security_alert_payload(
    alert_type: str,
    severity: str,  # "low", "medium", "high", "critical"
    source_ip: Optional[str] = None,
    source_node: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build payload for SecurityAlert event"""
    return {
        "alert_type": alert_type,
        "severity": severity,
        "source_ip": source_ip,
        "source_node": source_node,
        "details": details or {},
    }


def wireguard_peer_payload(
    peer_public_key: str,
    peer_ip: str,
    action: str,  # "added", "removed", "updated"
    node_id: Optional[int] = None,
    client_id: Optional[int] = None
) -> Dict[str, Any]:
    """Build payload for WireGuard peer events"""
    return {
        "peer_public_key": peer_public_key,
        "peer_ip": peer_ip,
        "action": action,
        "node_id": node_id,
        "client_id": client_id,
    }


def config_synced_payload(
    node_id: int,
    hostname: str,
    config_version: int,
    peer_count: int,
    acl_rule_count: int
) -> Dict[str, Any]:
    """Build payload for NodeConfigSynced event"""
    return {
        "node_id": node_id,
        "hostname": hostname,
        "config_version": config_version,
        "peer_count": peer_count,
        "acl_rule_count": acl_rule_count,
    }
