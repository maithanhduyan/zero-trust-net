// API Types for Zero Trust Dashboard

// ============= Node Types =============
export type NodeRole = 'hub' | 'app' | 'db' | 'ops' | 'monitor' | 'gateway' | 'client'
export type NodeStatus = 'pending' | 'active' | 'suspended' | 'revoked'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface Node {
    id: number
    hostname: string
    role: NodeRole
    description?: string
    public_key: string
    overlay_ip: string
    real_ip?: string
    listen_port: number
    status: NodeStatus
    agent_version?: string
    os_info?: string
    trust_score: number
    risk_level: RiskLevel
    config_version: number
    created_at: string
    updated_at: string
    last_seen?: string
}

export interface NodesResponse {
    nodes: Node[]
    total: number
}

// ============= Client Device Types =============
export type DeviceType = 'mobile' | 'laptop' | 'desktop' | 'other'
export type TunnelMode = 'full' | 'split'

export interface ClientDevice {
    id: number
    device_name: string
    device_type: DeviceType
    user_id?: string
    description?: string
    public_key: string
    overlay_ip: string
    tunnel_mode: TunnelMode
    status: NodeStatus
    config_token?: string
    config_downloaded: boolean
    created_at: string
    updated_at: string
    expires_at: string
    last_seen?: string
}

export interface ClientDevicesResponse {
    devices: ClientDevice[]
    total: number
}

// ============= User/Group Types =============
export type UserStatus = 'active' | 'suspended' | 'disabled'

export interface User {
    id: number
    username: string
    display_name?: string
    email?: string
    department?: string
    job_title?: string
    status: UserStatus
    groups?: string[]
    created_at: string
    updated_at: string
    last_login?: string
}

export interface Group {
    id: number
    name: string
    display_name?: string
    description?: string
    group_type: 'team' | 'department' | 'role' | 'custom'
    parent_group_id?: number
    member_count?: number
    status: 'active' | 'disabled'
    created_at: string
    updated_at: string
}

export interface GroupMembersResponse {
    members: User[]
}

export interface UserGroupsResponse {
    groups: Group[]
}

// ============= Policy Types =============
export type PolicyAction = 'allow' | 'deny' | 'require_mfa'

export interface AccessPolicy {
    id: number
    name: string
    description?: string
    source_role: string
    target_role: string
    ports?: number[]
    protocol?: 'tcp' | 'udp' | 'icmp' | 'any'
    action: PolicyAction
    priority: number
    enabled: boolean
    created_at: string
    updated_at: string
}

export interface PoliciesResponse {
    policies: AccessPolicy[]
    total: number
}

// User Access Policy
export type AccessAction = 'allow' | 'deny'

export interface UserAccessPolicy {
    id: number
    user_id: number
    target_resource: string
    action: AccessAction
    created_at: string
    updated_at: string
}

// ============= Event Types =============
export interface EventStoreEntry {
    id: number
    event_type: string
    aggregate_type: string
    aggregate_id: number
    version: number
    data: Record<string, unknown>
    timestamp: string
}

// ============= Network Stats =============
export interface NetworkStats {
    total_ips: number
    allocated_ips: number
    available_ips: number
    utilization_percent: number
}

export interface WireGuardPeer {
    public_key: string
    allowed_ips: string
    endpoint?: string
    latest_handshake?: string
    transfer_rx?: number
    transfer_tx?: number
}

// ============= API Responses =============
export interface HealthResponse {
    status: 'healthy' | 'degraded' | 'unhealthy'
    service: string
    version: string
    uptime_seconds: number
    database: string
    timestamp: string
}

export interface ApiError {
    success: false
    error: string
    error_code: string
    details?: Record<string, unknown>
    timestamp: string
}

// Access Evaluation
export interface AccessEvaluationRequest {
    user_id: string
    resource_type: string
    resource_value: string
    device_type?: DeviceType
    client_ip?: string
}

export interface AccessEvaluationResponse {
    allowed: boolean
    action: AccessAction
    matched_policy?: number
    reason: string
}
