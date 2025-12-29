# control-plane/api/v1/admin.py
"""
Admin API Endpoints
RESTful API for administrators to manage nodes and policies
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database.session import get_db
from database.models import Node, AccessPolicy, NodeStatus
from schemas.node import (
    NodeResponse,
    NodeUpdate,
    NodeListResponse,
)
from schemas.policy import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyListResponse,
)
from schemas.base import BaseResponse, ErrorResponse
from core.node_manager import node_manager
from core.policy_engine import policy_engine
from core.ipam import ipam_service
from core.agent_integrity import integrity_service
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# === Authentication Dependency ===

async def verify_admin_token(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """
    Verify admin authentication token

    In production, replace with proper JWT/OAuth2 authentication
    """
    if x_admin_token != settings.ADMIN_SECRET:
        logger.warning(f"Invalid admin token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Invalid or missing admin token",
                "error_code": "UNAUTHORIZED"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    return True


# === Node Management Endpoints ===

@router.get(
    "/nodes",
    response_model=NodeListResponse,
    summary="List all nodes",
    description="Get a list of all registered nodes with optional filtering"
)
async def list_nodes(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    role: Optional[str] = Query(None, description="Filter by role"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """List all nodes with optional filtering"""
    nodes = node_manager.get_all_nodes(db, status=status_filter, role=role)

    return NodeListResponse(
        nodes=[
            NodeResponse(
                id=node.id,
                hostname=node.hostname,
                role=node.role,
                status=node.status,
                overlay_ip=node.overlay_ip,
                real_ip=node.real_ip,
                public_key=node.public_key,
                description=node.description,
                agent_version=node.agent_version,
                os_info=node.os_info,
                last_seen=node.last_seen,
                created_at=node.created_at,
                updated_at=node.updated_at
            )
            for node in nodes
        ],
        total=len(nodes)
    )


@router.get(
    "/nodes/{node_id}",
    response_model=NodeResponse,
    responses={
        200: {"description": "Node found"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Get node by ID",
    description="Get detailed information about a specific node"
)
async def get_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Get node details by ID"""
    node = node_manager.get_node_by_id(db, node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Node with id {node_id} not found",
                "error_code": "NODE_NOT_FOUND"
            }
        )

    return NodeResponse(
        id=node.id,
        hostname=node.hostname,
        role=node.role,
        status=node.status,
        overlay_ip=node.overlay_ip,
        real_ip=node.real_ip,
        public_key=node.public_key,
        description=node.description,
        agent_version=node.agent_version,
        os_info=node.os_info,
        last_seen=node.last_seen,
        created_at=node.created_at,
        updated_at=node.updated_at
    )


@router.patch(
    "/nodes/{node_id}",
    response_model=NodeResponse,
    responses={
        200: {"description": "Node updated"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Update node",
    description="Update node information (description, status, role)"
)
async def update_node(
    node_id: int,
    node_update: NodeUpdate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Update node information"""
    node = node_manager.get_node_by_id(db, node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Node with id {node_id} not found",
                "error_code": "NODE_NOT_FOUND"
            }
        )

    # Update fields
    if node_update.description is not None:
        node.description = node_update.description
    if node_update.status is not None:
        node.status = node_update.status.value
        node.is_approved = node_update.status.value == NodeStatus.ACTIVE.value
    if node_update.role is not None:
        node.role = node_update.role.value

    db.commit()
    db.refresh(node)

    logger.info(f"Node {node.hostname} updated")

    return NodeResponse(
        id=node.id,
        hostname=node.hostname,
        role=node.role,
        status=node.status,
        overlay_ip=node.overlay_ip,
        real_ip=node.real_ip,
        public_key=node.public_key,
        description=node.description,
        agent_version=node.agent_version,
        os_info=node.os_info,
        last_seen=node.last_seen,
        created_at=node.created_at,
        updated_at=node.updated_at
    )


@router.post(
    "/nodes/{node_id}/approve",
    response_model=BaseResponse[NodeResponse],
    responses={
        200: {"description": "Node approved"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Approve node",
    description="Approve a pending node to join the network"
)
async def approve_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Approve a pending node"""
    try:
        node = node_manager.approve_node(db, node_id, admin_id="admin")

        return BaseResponse(
            success=True,
            message=f"Node {node.hostname} approved successfully",
            data=NodeResponse(
                id=node.id,
                hostname=node.hostname,
                role=node.role,
                status=node.status,
                overlay_ip=node.overlay_ip,
                real_ip=node.real_ip,
                public_key=node.public_key,
                description=node.description,
                agent_version=node.agent_version,
                os_info=node.os_info,
                last_seen=node.last_seen,
                created_at=node.created_at,
                updated_at=node.updated_at
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": str(e),
                "error_code": "NODE_NOT_FOUND"
            }
        )


@router.post(
    "/nodes/{node_id}/suspend",
    response_model=BaseResponse[NodeResponse],
    responses={
        200: {"description": "Node suspended"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Suspend node",
    description="Temporarily suspend an active node"
)
async def suspend_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Suspend an active node"""
    try:
        node = node_manager.suspend_node(db, node_id, admin_id="admin")

        return BaseResponse(
            success=True,
            message=f"Node {node.hostname} suspended",
            data=NodeResponse(
                id=node.id,
                hostname=node.hostname,
                role=node.role,
                status=node.status,
                overlay_ip=node.overlay_ip,
                real_ip=node.real_ip,
                public_key=node.public_key,
                description=node.description,
                agent_version=node.agent_version,
                os_info=node.os_info,
                last_seen=node.last_seen,
                created_at=node.created_at,
                updated_at=node.updated_at
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": str(e),
                "error_code": "NODE_NOT_FOUND"
            }
        )


@router.post(
    "/nodes/{node_id}/revoke",
    response_model=BaseResponse[NodeResponse],
    responses={
        200: {"description": "Node revoked"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Revoke node",
    description="Permanently revoke a node's access"
)
async def revoke_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Revoke a node permanently"""
    try:
        node = node_manager.revoke_node(db, node_id, admin_id="admin")

        return BaseResponse(
            success=True,
            message=f"Node {node.hostname} revoked",
            data=NodeResponse(
                id=node.id,
                hostname=node.hostname,
                role=node.role,
                status=node.status,
                overlay_ip=node.overlay_ip,
                real_ip=node.real_ip,
                public_key=node.public_key,
                description=node.description,
                agent_version=node.agent_version,
                os_info=node.os_info,
                last_seen=node.last_seen,
                created_at=node.created_at,
                updated_at=node.updated_at
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": str(e),
                "error_code": "NODE_NOT_FOUND"
            }
        )


# === Agent Integrity Management ===

@router.get(
    "/nodes/{node_id}/integrity",
    response_model=BaseResponse,
    responses={
        200: {"description": "Integrity status retrieved"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Get node integrity status",
    description="Get agent integrity verification status for a node"
)
async def get_node_integrity(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Get integrity status for a node"""
    node = node_manager.get_node_by_id(db, node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Node with id {node_id} not found",
                "error_code": "NODE_NOT_FOUND"
            }
        )

    return BaseResponse(
        success=True,
        message=f"Integrity status for {node.hostname}",
        data={
            "node_id": node.id,
            "hostname": node.hostname,
            "expected_hash": node.agent_hash,
            "last_reported_hash": node.last_reported_hash,
            "hash_verified": node.hash_verified,
            "hash_mismatch_count": node.hash_mismatch_count,
            "status": "verified" if node.hash_verified else (
                "pending" if not node.agent_hash else "mismatch"
            )
        }
    )


@router.post(
    "/nodes/{node_id}/integrity/approve",
    response_model=BaseResponse,
    responses={
        200: {"description": "Agent hash approved"},
        404: {"description": "Node not found", "model": ErrorResponse},
        400: {"description": "No hash to approve", "model": ErrorResponse},
    },
    summary="Approve agent hash",
    description="Approve the current reported agent hash as the expected hash for this node"
)
async def approve_agent_hash(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Approve agent's reported hash as the expected hash"""
    node = node_manager.get_node_by_id(db, node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Node with id {node_id} not found",
                "error_code": "NODE_NOT_FOUND"
            }
        )

    if not node.last_reported_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No hash reported by agent yet. Wait for agent heartbeat.",
                "error_code": "NO_HASH_REPORTED"
            }
        )

    success = integrity_service.approve_reported_hash(db, node)

    if success:
        logger.info(f"Admin approved agent hash for {node.hostname}")
        return BaseResponse(
            success=True,
            message=f"Agent hash approved for {node.hostname}",
            data={
                "node_id": node.id,
                "hostname": node.hostname,
                "approved_hash": node.agent_hash[:32] + "..." if node.agent_hash else None
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Failed to approve hash",
                "error_code": "APPROVAL_FAILED"
            }
        )


@router.put(
    "/nodes/{node_id}/integrity/hash",
    response_model=BaseResponse,
    responses={
        200: {"description": "Expected hash set"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Set expected agent hash",
    description="Manually set the expected agent hash for a node"
)
async def set_agent_hash(
    node_id: int,
    hash_value: str = Query(..., min_length=64, max_length=64, description="SHA-256 hash (64 hex chars)"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Set expected agent hash manually"""
    node = node_manager.get_node_by_id(db, node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Node with id {node_id} not found",
                "error_code": "NODE_NOT_FOUND"
            }
        )

    node.agent_hash = hash_value
    node.hash_mismatch_count = 0

    # Check if it matches the last reported hash
    if node.last_reported_hash == hash_value:
        node.hash_verified = True
    else:
        node.hash_verified = False

    db.commit()

    logger.info(f"Admin set agent hash for {node.hostname}: {hash_value[:16]}...")

    return BaseResponse(
        success=True,
        message=f"Expected hash set for {node.hostname}",
        data={
            "node_id": node.id,
            "hostname": node.hostname,
            "expected_hash": hash_value,
            "hash_verified": node.hash_verified
        }
    )


@router.post(
    "/integrity/global-hash",
    response_model=BaseResponse,
    summary="Set global expected agent hash",
    description="Set a global expected hash for all agents (used when node-specific hash not set)"
)
async def set_global_hash(
    hash_value: str = Query(..., min_length=64, max_length=64, description="SHA-256 hash (64 hex chars)"),
    _: bool = Depends(verify_admin_token)
):
    """Set global expected agent hash"""
    integrity_service.set_global_expected_hash(hash_value)

    logger.info(f"Admin set global agent hash: {hash_value[:16]}...")

    return BaseResponse(
        success=True,
        message="Global agent hash set successfully",
        data={
            "global_hash": hash_value
        }
    )


@router.delete(
    "/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Node deleted"},
        404: {"description": "Node not found", "model": ErrorResponse},
    },
    summary="Delete node",
    description="Permanently delete a node and release its IP"
)
async def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Delete a node"""
    if not node_manager.delete_node(db, node_id, admin_id="admin"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Node with id {node_id} not found",
                "error_code": "NODE_NOT_FOUND"
            }
        )

    return None


# === Policy Management Endpoints ===

@router.get(
    "/policies",
    response_model=PolicyListResponse,
    summary="List all policies",
    description="Get all access policies"
)
async def list_policies(
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """List all policies"""
    query = db.query(AccessPolicy)

    if enabled is not None:
        query = query.filter(AccessPolicy.enabled == enabled)

    policies = query.order_by(AccessPolicy.priority).all()

    return PolicyListResponse(
        policies=[
            PolicyResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                src_role=p.src_role,
                dst_role=p.dst_role,
                port=p.port,
                protocol=p.protocol,
                action=p.action,
                priority=p.priority,
                enabled=p.enabled,
                created_at=p.created_at,
                updated_at=p.updated_at
            )
            for p in policies
        ],
        total=len(policies)
    )


@router.post(
    "/policies",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Policy created"},
        400: {"description": "Invalid policy", "model": ErrorResponse},
        409: {"description": "Policy name exists", "model": ErrorResponse},
    },
    summary="Create policy",
    description="Create a new access policy"
)
async def create_policy(
    policy_in: PolicyCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Create a new policy"""
    # Validate policy
    is_valid, error = policy_engine.validate_policy(policy_in.model_dump())
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": error,
                "error_code": "INVALID_POLICY"
            }
        )

    # Check for duplicate name
    existing = db.query(AccessPolicy).filter(AccessPolicy.name == policy_in.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": f"Policy with name '{policy_in.name}' already exists",
                "error_code": "POLICY_EXISTS"
            }
        )

    # Create policy
    new_policy = AccessPolicy(
        name=policy_in.name,
        description=policy_in.description,
        src_role=policy_in.src_role,
        dst_role=policy_in.dst_role,
        port=policy_in.port,
        protocol=policy_in.protocol.value,
        action=policy_in.action.value,
        priority=policy_in.priority,
        enabled=policy_in.enabled
    )

    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)

    # Increment config version to notify agents
    policy_engine.increment_config_version()

    logger.info(f"Policy created: {new_policy.name}")

    return PolicyResponse(
        id=new_policy.id,
        name=new_policy.name,
        description=new_policy.description,
        src_role=new_policy.src_role,
        dst_role=new_policy.dst_role,
        port=new_policy.port,
        protocol=new_policy.protocol,
        action=new_policy.action,
        priority=new_policy.priority,
        enabled=new_policy.enabled,
        created_at=new_policy.created_at,
        updated_at=new_policy.updated_at
    )


@router.get(
    "/policies/{policy_id}",
    response_model=PolicyResponse,
    responses={
        200: {"description": "Policy found"},
        404: {"description": "Policy not found", "model": ErrorResponse},
    },
    summary="Get policy",
    description="Get a specific policy by ID"
)
async def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Get policy by ID"""
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Policy with id {policy_id} not found",
                "error_code": "POLICY_NOT_FOUND"
            }
        )

    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        src_role=policy.src_role,
        dst_role=policy.dst_role,
        port=policy.port,
        protocol=policy.protocol,
        action=policy.action,
        priority=policy.priority,
        enabled=policy.enabled,
        created_at=policy.created_at,
        updated_at=policy.updated_at
    )


@router.patch(
    "/policies/{policy_id}",
    response_model=PolicyResponse,
    responses={
        200: {"description": "Policy updated"},
        404: {"description": "Policy not found", "model": ErrorResponse},
    },
    summary="Update policy",
    description="Update an existing policy"
)
async def update_policy(
    policy_id: int,
    policy_update: PolicyUpdate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Update a policy"""
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Policy with id {policy_id} not found",
                "error_code": "POLICY_NOT_FOUND"
            }
        )

    # Update fields
    update_data = policy_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            if hasattr(value, 'value'):  # Enum
                setattr(policy, field, value.value)
            else:
                setattr(policy, field, value)

    db.commit()
    db.refresh(policy)

    # Increment config version
    policy_engine.increment_config_version()

    logger.info(f"Policy updated: {policy.name}")

    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        src_role=policy.src_role,
        dst_role=policy.dst_role,
        port=policy.port,
        protocol=policy.protocol,
        action=policy.action,
        priority=policy.priority,
        enabled=policy.enabled,
        created_at=policy.created_at,
        updated_at=policy.updated_at
    )


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Policy deleted"},
        404: {"description": "Policy not found", "model": ErrorResponse},
    },
    summary="Delete policy",
    description="Delete a policy"
)
async def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Delete a policy"""
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Policy with id {policy_id} not found",
                "error_code": "POLICY_NOT_FOUND"
            }
        )

    db.delete(policy)
    db.commit()

    # Increment config version
    policy_engine.increment_config_version()

    logger.info(f"Policy deleted: id={policy_id}")

    return None


# === Network Info Endpoints ===

@router.get(
    "/network/stats",
    summary="Get network statistics",
    description="Get IP allocation and network statistics"
)
async def get_network_stats(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Get network statistics"""
    return ipam_service.get_allocation_stats(db)


@router.get(
    "/network/allocations",
    summary="Get IP allocations",
    description="Get list of all IP allocations"
)
async def get_ip_allocations(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token)
):
    """Get all IP allocations"""
    allocations = ipam_service.get_used_ips(db)

    return {
        "allocations": [
            {"ip": ip, "hostname": hostname}
            for ip, hostname in allocations
        ],
        "total": len(allocations)
    }


# === WireGuard Management Endpoints ===

@router.post(
    "/wireguard/add-peer",
    summary="Add peer to Hub WireGuard",
    description="Automatically add a peer to the Hub's WireGuard interface"
)
async def add_wireguard_peer(
    peer_data: dict,
    _: bool = Depends(verify_admin_token)
):
    """
    Add a peer to Hub's WireGuard interface.

    This endpoint runs wg commands on the Hub server to add a new peer.
    """
    import subprocess

    public_key = peer_data.get("public_key")
    allowed_ips = peer_data.get("allowed_ips")
    comment = peer_data.get("comment", "")

    if not public_key or not allowed_ips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "public_key and allowed_ips are required",
                "error_code": "MISSING_FIELDS"
            }
        )

    try:
        # Add peer using wg command
        cmd_add = ["wg", "set", "wg0", "peer", public_key, "allowed-ips", allowed_ips]
        result_add = subprocess.run(cmd_add, capture_output=True, text=True, timeout=10)

        if result_add.returncode != 0:
            logger.error(f"Failed to add peer: {result_add.stderr}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": f"Failed to add peer: {result_add.stderr}",
                    "error_code": "WG_ADD_FAILED"
                }
            )

        # Save config
        cmd_save = ["wg-quick", "save", "wg0"]
        result_save = subprocess.run(cmd_save, capture_output=True, text=True, timeout=10)

        if result_save.returncode != 0:
            logger.warning(f"Failed to save config: {result_save.stderr}")

        logger.info(f"Added WireGuard peer: {public_key[:20]}... -> {allowed_ips} ({comment})")

        return {
            "success": True,
            "message": f"Peer added successfully",
            "peer": {
                "public_key": public_key,
                "allowed_ips": allowed_ips,
                "comment": comment
            }
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "WireGuard command timed out",
                "error_code": "WG_TIMEOUT"
            }
        )
    except Exception as e:
        logger.error(f"Error adding peer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e),
                "error_code": "WG_ERROR"
            }
        )


@router.get(
    "/wireguard/peers",
    summary="List WireGuard peers",
    description="Get list of all WireGuard peers on Hub"
)
async def list_wireguard_peers(
    _: bool = Depends(verify_admin_token)
):
    """List all WireGuard peers on Hub"""
    import subprocess

    try:
        result = subprocess.run(
            ["wg", "show", "wg0", "dump"],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "Failed to get peers", "error_code": "WG_ERROR"}
            )

        peers = []
        lines = result.stdout.strip().split('\n')

        # Skip first line (interface info)
        for line in lines[1:]:
            if line:
                parts = line.split('\t')
                if len(parts) >= 4:
                    peers.append({
                        "public_key": parts[0],
                        "endpoint": parts[2] if parts[2] != "(none)" else None,
                        "allowed_ips": parts[3],
                        "latest_handshake": int(parts[4]) if len(parts) > 4 and parts[4] != "0" else None,
                        "transfer_rx": int(parts[5]) if len(parts) > 5 else 0,
                        "transfer_tx": int(parts[6]) if len(parts) > 6 else 0,
                    })

        return {
            "success": True,
            "peers": peers,
            "total": len(peers)
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "Command timed out", "error_code": "WG_TIMEOUT"}
        )


@router.delete(
    "/wireguard/peers/{public_key}",
    summary="Remove WireGuard peer",
    description="Remove a peer from Hub's WireGuard interface"
)
async def remove_wireguard_peer(
    public_key: str,
    _: bool = Depends(verify_admin_token)
):
    """Remove a WireGuard peer from Hub"""
    import subprocess
    import urllib.parse

    # URL decode the public key
    decoded_key = urllib.parse.unquote(public_key)

    try:
        cmd = ["wg", "set", "wg0", "peer", decoded_key, "remove"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": f"Failed to remove peer: {result.stderr}", "error_code": "WG_ERROR"}
            )

        # Save config
        subprocess.run(["wg-quick", "save", "wg0"], capture_output=True, timeout=10)

        logger.info(f"Removed WireGuard peer: {decoded_key[:20]}...")

        return {
            "success": True,
            "message": "Peer removed successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "WG_ERROR"}
        )