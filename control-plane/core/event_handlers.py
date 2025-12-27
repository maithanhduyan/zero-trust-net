# control-plane/core/event_handlers.py
"""
Event Handlers - React to domain events

These handlers are decoupled from event publishers.
Each handler has a single responsibility.
"""

import json
import logging
from typing import Optional
from sqlalchemy.orm import Session

from .events import Event, EventPriority, event_bus
from .domain_events import EventTypes
from database.session import get_db_session

logger = logging.getLogger(__name__)


# =============================================================================
# Event Store Handler - Persist all events
# =============================================================================

def persist_event(event: Event) -> None:
    """
    Persist event to EventStore table for audit trail and replay

    This handler runs for ALL events with HIGH priority.
    """
    from database.models import EventStore

    db = get_db_session()
    try:
        # Determine aggregate type and ID from payload
        aggregate_type = None
        aggregate_id = None

        if "node_id" in event.payload:
            aggregate_type = "Node"
            aggregate_id = str(event.payload["node_id"])
        elif "device_id" in event.payload:
            aggregate_type = "ClientDevice"
            aggregate_id = str(event.payload["device_id"])
        elif "policy_id" in event.payload:
            aggregate_type = "Policy"
            aggregate_id = str(event.payload["policy_id"])
        elif "group_id" in event.payload and event.event_type.startswith("Group"):
            aggregate_type = "Group"
            aggregate_id = str(event.payload["group_id"])
        elif "user_id" in event.payload and event.event_type.startswith("User"):
            aggregate_type = "User"
            aggregate_id = str(event.payload["user_id"])

        stored_event = EventStore(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=json.dumps(event.payload),
            source=event.source,
            version=event.version,
            processed=True,
            process_count=1
        )

        db.add(stored_event)
        db.commit()

        logger.debug(f"Event persisted: {event.event_type} (id={event.event_id})")

    except Exception as e:
        logger.error(f"Failed to persist event: {e}")
        db.rollback()
    finally:
        db.close()


# =============================================================================
# Audit Handler - Log all events for audit trail
# =============================================================================

def audit_handler(event: Event) -> None:
    """
    Log all events to audit trail

    This handler runs for ALL events with HIGH priority
    to ensure audit logging happens before any other processing.
    """
    logger.info(
        f"[AUDIT] {event.event_type} | "
        f"id={event.event_id} | "
        f"source={event.source} | "
        f"payload={event.payload}"
    )


# =============================================================================
# WireGuard Handlers - Sync WireGuard state
# =============================================================================

def on_node_registered(event: Event) -> None:
    """
    Add WireGuard peer when node is registered

    Called after a node successfully registers with the control plane.
    """
    payload = event.payload
    logger.info(f"Adding WireGuard peer for node {payload.get('hostname')}")

    # Import here to avoid circular dependency
    from .wireguard_service import wireguard_service

    try:
        public_key = payload.get("public_key")
        overlay_ip = payload.get("overlay_ip")

        if public_key and overlay_ip:
            # Extract IP without CIDR for allowed_ips
            ip_only = overlay_ip.split("/")[0] if "/" in overlay_ip else overlay_ip
            wireguard_service.add_peer(public_key, f"{ip_only}/32")
            logger.info(f"WireGuard peer added: {payload.get('hostname')} -> {overlay_ip}")
    except Exception as e:
        logger.error(f"Failed to add WireGuard peer: {e}")
        raise  # Let retry mechanism handle it


def on_node_revoked(event: Event) -> None:
    """
    Remove WireGuard peer when node is revoked
    """
    payload = event.payload
    logger.info(f"Removing WireGuard peer for node {payload.get('hostname')}")

    from .wireguard_service import wireguard_service

    try:
        public_key = payload.get("public_key")
        if public_key:
            wireguard_service.remove_peer(public_key)
            logger.info(f"WireGuard peer removed: {payload.get('hostname')}")
    except Exception as e:
        logger.error(f"Failed to remove WireGuard peer: {e}")
        raise


def on_client_device_created(event: Event) -> None:
    """
    Add WireGuard peer when client device is created
    """
    payload = event.payload
    logger.info(f"Adding WireGuard peer for client device {payload.get('device_name')}")

    from .wireguard_service import wireguard_service

    try:
        public_key = payload.get("public_key")
        overlay_ip = payload.get("overlay_ip")

        if public_key and overlay_ip:
            ip_only = overlay_ip.split("/")[0] if "/" in overlay_ip else overlay_ip
            wireguard_service.add_peer(public_key, f"{ip_only}/32")
            logger.info(f"WireGuard peer added for client: {payload.get('device_name')}")
    except Exception as e:
        logger.error(f"Failed to add WireGuard peer for client: {e}")
        raise


def on_client_device_revoked(event: Event) -> None:
    """
    Remove WireGuard peer when client device is revoked
    """
    payload = event.payload
    logger.info(f"Removing WireGuard peer for client {payload.get('device_name')}")

    from .wireguard_service import wireguard_service

    try:
        public_key = payload.get("public_key")
        if public_key:
            wireguard_service.remove_peer(public_key)
            logger.info(f"WireGuard peer removed for client: {payload.get('device_name')}")
    except Exception as e:
        logger.error(f"Failed to remove WireGuard peer for client: {e}")
        raise


# =============================================================================
# Notification Handlers - Notify other nodes
# =============================================================================

def on_config_changed(event: Event) -> None:
    """
    Notify agents when configuration changes

    This handler triggers config version increment
    so agents know to fetch new config on next sync.
    """
    logger.info(f"Config changed, incrementing version")

    # TODO: With WebSocket, push notification to connected agents
    # For now, agents will pick up changes on next poll

    # Increment config version in database
    db = get_db_session()
    try:
        from database.models import ConfigVersion
        version = db.query(ConfigVersion).first()
        if version:
            version.version += 1
            db.commit()
            logger.info(f"Config version incremented to {version.version}")
    except Exception as e:
        logger.error(f"Failed to increment config version: {e}")
    finally:
        db.close()


# =============================================================================
# Trust Score Handlers
# =============================================================================

def on_trust_score_changed(event: Event) -> None:
    """
    React to trust score changes

    May trigger automatic suspension if score drops below threshold.
    """
    payload = event.payload
    new_score = payload.get("new_score", 1.0)
    node_id = payload.get("node_id")
    hostname = payload.get("hostname")

    # Auto-suspend if trust score drops below critical threshold
    CRITICAL_THRESHOLD = 0.3

    if new_score < CRITICAL_THRESHOLD:
        logger.warning(
            f"Trust score for {hostname} dropped to {new_score} (below {CRITICAL_THRESHOLD}). "
            f"Consider automatic suspension."
        )

        # TODO: Implement automatic suspension
        # from .node_manager import node_manager
        # node_manager.suspend_node(db, node_id, reason="Low trust score")


# =============================================================================
# IP Management Handlers
# =============================================================================

def on_ip_pool_low(event: Event) -> None:
    """
    Alert when IP pool is running low
    """
    payload = event.payload
    available = payload.get("available", 0)
    total = payload.get("total", 0)

    logger.warning(
        f"IP pool running low: {available}/{total} addresses remaining "
        f"({payload.get('utilization_percent', 0)}% utilized)"
    )

    # TODO: Send notification to admin (email, Slack, etc.)


# =============================================================================
# Register All Handlers
# =============================================================================

def register_event_handlers() -> None:
    """
    Register all event handlers with the event bus

    Call this during application startup.
    """
    logger.info("Registering event handlers...")

    # Event persistence handler - store ALL events to EventStore
    # Register for all event types
    for event_type in [
        EventTypes.NODE_REGISTERED,
        EventTypes.NODE_APPROVED,
        EventTypes.NODE_SUSPENDED,
        EventTypes.NODE_REVOKED,
        EventTypes.CLIENT_DEVICE_CREATED,
        EventTypes.CLIENT_DEVICE_REVOKED,
        EventTypes.POLICY_CREATED,
        EventTypes.POLICY_UPDATED,
        EventTypes.POLICY_DELETED,
        EventTypes.SECURITY_ALERT,
        EventTypes.TRUST_SCORE_CHANGED,
        EventTypes.IP_ALLOCATED,
        EventTypes.IP_POOL_LOW,
        # User/Group events
        EventTypes.USER_CREATED,
        EventTypes.USER_UPDATED,
        EventTypes.USER_SUSPENDED,
        EventTypes.USER_DELETED,
        EventTypes.GROUP_CREATED,
        EventTypes.GROUP_UPDATED,
        EventTypes.GROUP_DELETED,
        EventTypes.USER_ADDED_TO_GROUP,
        EventTypes.USER_REMOVED_FROM_GROUP,
    ]:
        event_bus.subscribe(event_type, persist_event, EventPriority.HIGH)

    # Audit handler for important events
    event_bus.subscribe(EventTypes.NODE_REGISTERED, audit_handler, EventPriority.HIGH)
    event_bus.subscribe(EventTypes.NODE_REVOKED, audit_handler, EventPriority.HIGH)
    event_bus.subscribe(EventTypes.CLIENT_DEVICE_CREATED, audit_handler, EventPriority.HIGH)
    event_bus.subscribe(EventTypes.CLIENT_DEVICE_REVOKED, audit_handler, EventPriority.HIGH)
    event_bus.subscribe(EventTypes.POLICY_UPDATED, audit_handler, EventPriority.HIGH)
    event_bus.subscribe(EventTypes.SECURITY_ALERT, audit_handler, EventPriority.HIGH)

    # WireGuard sync handlers
    event_bus.subscribe(EventTypes.NODE_REGISTERED, on_node_registered, EventPriority.NORMAL)
    event_bus.subscribe(EventTypes.NODE_REVOKED, on_node_revoked, EventPriority.NORMAL)
    event_bus.subscribe(EventTypes.CLIENT_DEVICE_CREATED, on_client_device_created, EventPriority.NORMAL)
    event_bus.subscribe(EventTypes.CLIENT_DEVICE_REVOKED, on_client_device_revoked, EventPriority.NORMAL)

    # Config change notifications
    event_bus.subscribe(EventTypes.NODE_REGISTERED, on_config_changed, EventPriority.LOW)
    event_bus.subscribe(EventTypes.NODE_REVOKED, on_config_changed, EventPriority.LOW)
    event_bus.subscribe(EventTypes.POLICY_UPDATED, on_config_changed, EventPriority.LOW)

    # Trust score monitoring
    event_bus.subscribe(EventTypes.TRUST_SCORE_CHANGED, on_trust_score_changed, EventPriority.NORMAL)

    # IP pool monitoring
    event_bus.subscribe(EventTypes.IP_POOL_LOW, on_ip_pool_low, EventPriority.HIGH)

    subscriptions = event_bus.get_subscriptions()
    logger.info(f"Registered handlers: {subscriptions}")
