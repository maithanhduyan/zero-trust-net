# control-plane/schemas/user_policy.py
"""
Pydantic Schemas for User/Group Access Policies
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# User Schemas
# =============================================================================

class UserCreate(BaseModel):
    """Schema for creating a new user"""
    user_id: str = Field(..., min_length=1, max_length=100, description="Unique user identifier")
    email: Optional[str] = Field(None, max_length=255, description="User email address")
    display_name: Optional[str] = Field(None, max_length=100, description="Display name")
    department: Optional[str] = Field(None, max_length=100, description="Department/team")
    job_title: Optional[str] = Field(None, max_length=100, description="Job title")
    attributes: Optional[Dict[str, Any]] = Field(None, description="Custom attributes")


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, pattern="^(active|suspended|disabled)$")
    attributes: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    """Schema for user response"""
    id: int
    user_id: str
    display_name: Optional[str]
    email: Optional[str]
    department: Optional[str]
    job_title: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# =============================================================================
# Group Schemas
# =============================================================================

class GroupCreate(BaseModel):
    """Schema for creating a new group"""
    name: str = Field(..., min_length=1, max_length=100, description="Unique group name")
    display_name: Optional[str] = Field(None, max_length=100, description="Display name")
    description: Optional[str] = Field(None, description="Group description")
    group_type: str = Field("team", pattern="^(team|department|role|custom)$")
    parent_group_id: Optional[int] = Field(None, description="Parent group ID for nesting")


class GroupUpdate(BaseModel):
    """Schema for updating a group"""
    display_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    group_type: Optional[str] = Field(None, pattern="^(team|department|role|custom)$")
    status: Optional[str] = Field(None, pattern="^(active|disabled)$")


class GroupResponse(BaseModel):
    """Schema for group response"""
    id: int
    name: str
    display_name: Optional[str]
    description: Optional[str]
    group_type: str
    parent_group_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroupMembershipRequest(BaseModel):
    """Schema for adding/updating group membership"""
    user_id: str = Field(..., description="User ID to add")
    role: str = Field("member", pattern="^(member|admin|owner)$")


# =============================================================================
# Policy Schemas
# =============================================================================

class PolicyConditions(BaseModel):
    """Schema for policy conditions"""
    device_types: Optional[List[str]] = Field(
        None,
        description="Allowed device types: mobile, laptop, desktop"
    )
    time_windows: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Time-based access windows"
    )
    allowed_ips: Optional[List[str]] = Field(
        None,
        description="Allowed client IP ranges (CIDR notation)"
    )
    require_vpn: Optional[bool] = Field(
        None,
        description="Require VPN connection"
    )


class PolicyCreate(BaseModel):
    """Schema for creating an access policy"""
    name: str = Field(..., min_length=1, max_length=100, description="Policy name")
    description: Optional[str] = Field(None, description="Policy description")

    subject_type: str = Field(
        ...,
        pattern="^(user|group|all)$",
        description="Subject type: user, group, or all"
    )
    subject_id: Optional[int] = Field(
        None,
        description="User or Group ID (required if subject_type is user/group)"
    )

    resource_type: str = Field(
        ...,
        pattern="^(domain|ip_range|zone|service|url_pattern)$",
        description="Resource type"
    )
    resource_value: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Resource value (domain, IP range, zone name, etc.)"
    )

    action: str = Field(
        "allow",
        pattern="^(allow|deny|require_mfa)$",
        description="Policy action"
    )

    conditions: Optional[PolicyConditions] = Field(
        None,
        description="Optional conditions for the policy"
    )

    priority: int = Field(
        100,
        ge=1,
        le=1000,
        description="Priority (1-1000, lower = higher priority)"
    )

    valid_from: Optional[datetime] = Field(None, description="Policy valid from")
    valid_until: Optional[datetime] = Field(None, description="Policy valid until")

    @field_validator('subject_id')
    @classmethod
    def validate_subject_id(cls, v, info):
        subject_type = info.data.get('subject_type')
        if subject_type in ('user', 'group') and v is None:
            raise ValueError(f"subject_id is required when subject_type is {subject_type}")
        return v


class PolicyUpdate(BaseModel):
    """Schema for updating a policy"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    resource_value: Optional[str] = Field(None, min_length=1, max_length=255)
    action: Optional[str] = Field(None, pattern="^(allow|deny|require_mfa)$")
    conditions: Optional[PolicyConditions] = None
    priority: Optional[int] = Field(None, ge=1, le=1000)
    enabled: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class PolicyResponse(BaseModel):
    """Schema for policy response"""
    id: int
    name: str
    description: Optional[str]
    subject_type: str
    subject_id: Optional[int]
    resource_type: str
    resource_value: str
    action: str
    conditions: Optional[str]
    priority: int
    enabled: bool
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


# =============================================================================
# Access Evaluation Schemas
# =============================================================================

class AccessEvaluationRequest(BaseModel):
    """Schema for access evaluation request"""
    user_id: str = Field(..., description="User to evaluate")
    resource_type: str = Field(
        ...,
        pattern="^(domain|ip_range|zone|service|url_pattern)$"
    )
    resource_value: str = Field(..., description="Resource being accessed")
    device_type: Optional[str] = Field(None, description="Device type")
    client_ip: Optional[str] = Field(None, description="Client IP address")


class AccessEvaluationResponse(BaseModel):
    """Schema for access evaluation response"""
    allowed: bool
    action: str
    matched_policy: Optional[int]
    reason: str


# =============================================================================
# Bulk Operations
# =============================================================================

class BulkUserGroupRequest(BaseModel):
    """Schema for bulk adding users to a group"""
    user_ids: List[str] = Field(..., min_length=1, description="List of user IDs")
    role: str = Field("member", pattern="^(member|admin|owner)$")


class PolicyTemplateRequest(BaseModel):
    """Schema for creating policy from template"""
    template_name: str = Field(
        ...,
        pattern="^(internet_access|internal_only|business_hours|vpn_required)$",
        description="Template name"
    )
    subject_type: str = Field(..., pattern="^(user|group|all)$")
    subject_id: Optional[int] = None
    resource_value: str = Field(..., description="Resource to apply template to")
