# control-plane/api/v1/user_policy.py
"""
User/Group Access Policy API Endpoints

Provides REST API for:
- User management (CRUD)
- Group management (CRUD)
- User-Group membership
- Access policy management
- Policy evaluation
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session

from database.session import get_db
from core.user_policy_manager import user_policy_manager
from schemas.user_policy import (
    UserCreate, UserUpdate, UserResponse,
    GroupCreate, GroupUpdate, GroupResponse, GroupMembershipRequest,
    PolicyCreate, PolicyUpdate, PolicyResponse,
    AccessEvaluationRequest, AccessEvaluationResponse,
    BulkUserGroupRequest
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Authentication
# =============================================================================

def verify_admin_token(x_admin_token: str = Header(...)):
    """Verify admin authentication token"""
    if x_admin_token != settings.ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return x_admin_token


# =============================================================================
# User Endpoints
# =============================================================================

@router.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Create a new user"""
    try:
        result = user_policy_manager.create_user(
            db,
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            department=user.department,
            job_title=user.job_title,
            attributes=user.attributes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users", response_model=List[UserResponse])
def list_users(
    status: Optional[str] = Query(None, pattern="^(active|suspended|disabled)$"),
    department: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """List all users with optional filtering"""
    return user_policy_manager.list_users(
        db, status=status, department=department, limit=limit, offset=offset
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Get a specific user by ID"""
    user = user_policy_manager.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    updates: UserUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Update a user"""
    result = user_policy_manager.update_user(
        db, user_id, **updates.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return result


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Delete a user"""
    if not user_policy_manager.delete_user(db, user_id):
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return {"success": True, "message": f"User {user_id} deleted"}


@router.get("/users/{user_id}/groups", response_model=List[GroupResponse])
def get_user_groups(
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Get all groups a user belongs to"""
    user = user_policy_manager.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user_policy_manager.get_user_groups(db, user_id)


# =============================================================================
# Group Endpoints
# =============================================================================

@router.post("/groups", response_model=GroupResponse)
def create_group(
    group: GroupCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Create a new group"""
    try:
        result = user_policy_manager.create_group(
            db,
            name=group.name,
            display_name=group.display_name,
            description=group.description,
            group_type=group.group_type,
            parent_group_id=group.parent_group_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/groups", response_model=List[GroupResponse])
def list_groups(
    group_type: Optional[str] = Query(None, pattern="^(team|department|role|custom)$"),
    parent_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """List all groups with optional filtering"""
    return user_policy_manager.list_groups(db, group_type=group_type, parent_id=parent_id)


@router.get("/groups/{group_name}", response_model=GroupResponse)
def get_group(
    group_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Get a specific group by name"""
    group = user_policy_manager.get_group(db, group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_name} not found")
    return group


@router.patch("/groups/{group_name}", response_model=GroupResponse)
def update_group(
    group_name: str,
    updates: GroupUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Update a group"""
    group = user_policy_manager.get_group(db, group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_name} not found")

    # Apply updates directly to the model
    for field, value in updates.model_dump(exclude_none=True).items():
        setattr(group, field, value)
    group.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_name}")
def delete_group(
    group_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Delete a group"""
    from database.models import Group, UserGroupMembership

    group = user_policy_manager.get_group(db, group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_name} not found")

    # Remove all memberships
    db.query(UserGroupMembership).filter(UserGroupMembership.group_id == group.id).delete()
    db.delete(group)
    db.commit()

    return {"success": True, "message": f"Group {group_name} deleted"}


@router.get("/groups/{group_name}/members", response_model=List[UserResponse])
def get_group_members(
    group_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Get all members of a group"""
    group = user_policy_manager.get_group(db, group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_name} not found")
    return user_policy_manager.get_group_members(db, group_name)


@router.post("/groups/{group_name}/members")
def add_member_to_group(
    group_name: str,
    membership: GroupMembershipRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Add a user to a group"""
    if not user_policy_manager.add_user_to_group(db, membership.user_id, group_name, membership.role):
        raise HTTPException(status_code=404, detail="User or group not found")
    return {"success": True, "message": f"User {membership.user_id} added to {group_name}"}


@router.delete("/groups/{group_name}/members/{user_id}")
def remove_member_from_group(
    group_name: str,
    user_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Remove a user from a group"""
    if not user_policy_manager.remove_user_from_group(db, user_id, group_name):
        raise HTTPException(status_code=404, detail="User or group not found")
    return {"success": True, "message": f"User {user_id} removed from {group_name}"}


@router.post("/groups/{group_name}/members/bulk")
def bulk_add_members(
    group_name: str,
    request: BulkUserGroupRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Add multiple users to a group"""
    group = user_policy_manager.get_group(db, group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_name} not found")

    added = []
    failed = []

    for user_id in request.user_ids:
        if user_policy_manager.add_user_to_group(db, user_id, group_name, request.role):
            added.append(user_id)
        else:
            failed.append(user_id)

    return {
        "success": True,
        "added": added,
        "failed": failed,
        "message": f"Added {len(added)} users to {group_name}"
    }


# =============================================================================
# Policy Endpoints
# =============================================================================

@router.post("/policies", response_model=PolicyResponse)
def create_policy(
    policy: PolicyCreate,
    db: Session = Depends(get_db),
    admin_token: str = Depends(verify_admin_token)
):
    """Create a new access policy"""
    try:
        result = user_policy_manager.create_policy(
            db,
            name=policy.name,
            description=policy.description,
            subject_type=policy.subject_type,
            subject_id=policy.subject_id,
            resource_type=policy.resource_type,
            resource_value=policy.resource_value,
            action=policy.action,
            conditions=policy.conditions.model_dump() if policy.conditions else None,
            priority=policy.priority,
            valid_from=policy.valid_from,
            valid_until=policy.valid_until,
            created_by="admin"  # TODO: Extract from token
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/policies", response_model=List[PolicyResponse])
def list_policies(
    subject_type: Optional[str] = Query(None, pattern="^(user|group|all)$"),
    subject_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """List all policies with optional filtering"""
    return user_policy_manager.list_policies(
        db,
        subject_type=subject_type,
        subject_id=subject_id,
        resource_type=resource_type,
        enabled_only=not include_disabled
    )


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Get a specific policy by ID"""
    policy = user_policy_manager.get_policy(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: int,
    updates: PolicyUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Update a policy"""
    update_dict = updates.model_dump(exclude_none=True)
    if 'conditions' in update_dict and update_dict['conditions']:
        update_dict['conditions'] = update_dict['conditions']

    result = user_policy_manager.update_policy(db, policy_id, **update_dict)
    if not result:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return result


@router.delete("/policies/{policy_id}")
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Delete a policy"""
    if not user_policy_manager.delete_policy(db, policy_id):
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return {"success": True, "message": f"Policy {policy_id} deleted"}


# =============================================================================
# Policy Evaluation Endpoints
# =============================================================================

@router.post("/evaluate", response_model=AccessEvaluationResponse)
def evaluate_access(
    request: AccessEvaluationRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """
    Evaluate whether a user can access a resource

    This is the core Zero Trust decision point.
    Returns allow/deny with the matching policy.
    """
    result = user_policy_manager.evaluate_access(
        db,
        user_id=request.user_id,
        resource_type=request.resource_type,
        resource_value=request.resource_value,
        device_type=request.device_type,
        client_ip=request.client_ip
    )
    return AccessEvaluationResponse(**result)


@router.get("/evaluate/{user_id}/domain/{domain}")
def quick_domain_check(
    user_id: str,
    domain: str,
    device_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token)
):
    """Quick check if a user can access a domain"""
    result = user_policy_manager.evaluate_access(
        db,
        user_id=user_id,
        resource_type="domain",
        resource_value=domain,
        device_type=device_type
    )
    return result


# =============================================================================
# Policy Templates
# =============================================================================

@router.get("/templates")
def list_policy_templates(
    _: str = Depends(verify_admin_token)
):
    """List available policy templates"""
    return {
        "templates": [
            {
                "name": "internet_access",
                "description": "Allow full internet access",
                "action": "allow",
                "resource_type": "domain",
                "resource_value": "*"
            },
            {
                "name": "internal_only",
                "description": "Allow access to internal resources only",
                "action": "allow",
                "resource_type": "zone",
                "resource_value": "internal"
            },
            {
                "name": "business_hours",
                "description": "Allow access during business hours (Mon-Fri 9-18)",
                "action": "allow",
                "conditions": {
                    "time_windows": [
                        {"days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00"}
                    ]
                }
            },
            {
                "name": "vpn_required",
                "description": "Require VPN connection for access",
                "action": "allow",
                "conditions": {
                    "require_vpn": True
                }
            }
        ]
    }
