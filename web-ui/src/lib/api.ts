import axios, { AxiosInstance, AxiosError } from 'axios'
import type {
    Node,
    ClientDevice,
    User,
    Group,
    AccessPolicy,
    UserAccessPolicy,
    NetworkStats,
    WireGuardPeer,
    HealthResponse,
    AccessEvaluationRequest,
    AccessEvaluationResponse,
    GroupMembersResponse,
    UserGroupsResponse,
    EventStoreEntry,
} from '@/types'

// API Configuration
const API_URL = import.meta.env.VITE_API_URL || '/api/v1'
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || ''

// Create axios instance
const api: AxiosInstance = axios.create({
    baseURL: API_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Add admin token to all requests
api.interceptors.request.use((config) => {
    if (ADMIN_TOKEN) {
        config.headers['X-Admin-Token'] = ADMIN_TOKEN
    }
    return config
})

// Error handler
api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message)
        throw error
    }
)

// ============= Health =============
export const getHealth = async (): Promise<HealthResponse> => {
    const { data } = await api.get('/health')
    return data
}

// ============= Nodes =============
export const getNodes = async (): Promise<Node[]> => {
    const { data } = await api.get('/admin/nodes')
    return Array.isArray(data) ? data : data.nodes || []
}

export const getNode = async (id: number): Promise<Node> => {
    const { data } = await api.get(`/admin/nodes/${id}`)
    return data
}

export const updateNode = async (
    id: number,
    updates: Partial<Pick<Node, 'description' | 'status' | 'role'>>
): Promise<Node> => {
    const { data } = await api.patch(`/admin/nodes/${id}`, updates)
    return data
}

export const approveNode = async (id: number): Promise<Node> => {
    const { data } = await api.post(`/admin/nodes/${id}/approve`)
    return data
}

export const suspendNode = async (id: number): Promise<Node> => {
    const { data } = await api.post(`/admin/nodes/${id}/suspend`)
    return data
}

export const revokeNode = async (id: number): Promise<Node> => {
    const { data } = await api.post(`/admin/nodes/${id}/revoke`)
    return data
}

export const deleteNode = async (id: number): Promise<void> => {
    await api.delete(`/admin/nodes/${id}`)
}

// ============= Client Devices =============
export const getClientDevices = async (): Promise<ClientDevice[]> => {
    const { data } = await api.get('/client/devices')
    return Array.isArray(data) ? data : data.devices || []
}

export const getClientDevice = async (id: number): Promise<ClientDevice> => {
    const { data } = await api.get(`/client/devices/${id}`)
    return data
}

export const createClientDevice = async (device: {
    device_name: string
    device_type: string
    user_id?: string
    tunnel_mode?: string
    expires_days?: number
    description?: string
}): Promise<ClientDevice> => {
    const { data } = await api.post('/client/devices', device)
    return data
}

export const revokeClientDevice = async (id: number): Promise<void> => {
    await api.delete(`/client/devices/${id}`)
}

// ============= Users =============
export const getUsers = async (): Promise<User[]> => {
    const { data } = await api.get('/access/users')
    return Array.isArray(data) ? data : data.users || []
}

export const getUser = async (userId: number): Promise<User> => {
    const { data } = await api.get(`/access/users/${userId}`)
    return data
}

export const createUser = async (user: {
    username: string
    email?: string
    display_name?: string
    department?: string
    job_title?: string
}): Promise<User> => {
    const { data } = await api.post('/access/users', user)
    return data
}

export const updateUser = async (
    userId: number,
    updates: Partial<Omit<User, 'id' | 'username' | 'created_at' | 'updated_at'>>
): Promise<User> => {
    const { data } = await api.patch(`/access/users/${userId}`, updates)
    return data
}

export const deleteUser = async (userId: number): Promise<void> => {
    await api.delete(`/access/users/${userId}`)
}

export const getUserGroups = async (userId: number): Promise<UserGroupsResponse> => {
    const { data } = await api.get(`/access/users/${userId}/groups`)
    return data
}

// ============= Groups =============
export const getGroups = async (): Promise<Group[]> => {
    const { data } = await api.get('/access/groups')
    return Array.isArray(data) ? data : data.groups || []
}

export const getGroup = async (id: number): Promise<Group> => {
    const { data } = await api.get(`/access/groups/${id}`)
    return data
}

export const createGroup = async (group: {
    name: string
    display_name?: string
    description?: string
    group_type?: string
}): Promise<Group> => {
    const { data } = await api.post('/access/groups', group)
    return data
}

export const deleteGroup = async (id: number): Promise<void> => {
    await api.delete(`/access/groups/${id}`)
}

export const getGroupMembers = async (id: number): Promise<GroupMembersResponse> => {
    const { data } = await api.get(`/access/groups/${id}/members`)
    return data
}

export const addGroupMember = async (
    groupId: number,
    userId: number
): Promise<{ success: boolean; message: string }> => {
    const { data } = await api.post(`/access/groups/${groupId}/members`, {
        user_id: userId,
    })
    return data
}

export const removeGroupMember = async (
    groupId: number,
    userId: number
): Promise<void> => {
    await api.delete(`/access/groups/${groupId}/members/${userId}`)
}

// ============= Access Policies (Role-based) =============
export const getPolicies = async (): Promise<AccessPolicy[]> => {
    const { data } = await api.get('/admin/policies')
    return Array.isArray(data) ? data : data.policies || []
}

export const createPolicy = async (policy: {
    name: string
    source_role: string
    target_role: string
    ports?: number[]
    protocol?: string
    action: string
    priority?: number
    enabled?: boolean
}): Promise<AccessPolicy> => {
    const { data } = await api.post('/admin/policies', policy)
    return data
}

export const deletePolicy = async (id: number): Promise<void> => {
    await api.delete(`/admin/policies/${id}`)
}

// ============= User Access Policies =============
export const getUserAccessPolicies = async (): Promise<UserAccessPolicy[]> => {
    const { data } = await api.get('/access/policies')
    return Array.isArray(data) ? data : data.policies || []
}

export const createUserAccessPolicy = async (policy: {
    user_id: number
    target_resource: string
    action: string
}): Promise<UserAccessPolicy> => {
    const { data } = await api.post('/access/policies', policy)
    return data
}

export const deleteUserAccessPolicy = async (id: number): Promise<void> => {
    await api.delete(`/access/policies/${id}`)
}

export const evaluateAccess = async (
    request: AccessEvaluationRequest
): Promise<AccessEvaluationResponse> => {
    const { data } = await api.post('/access/evaluate', request)
    return data
}

// ============= Network Stats =============
export const getNetworkStats = async (): Promise<NetworkStats> => {
    const { data } = await api.get('/admin/network/stats')
    return data
}

export const getWireGuardPeers = async (): Promise<WireGuardPeer[]> => {
    const { data } = await api.get('/admin/wireguard/peers')
    return data
}

// ============= WebSocket Agents =============
export const getConnectedAgents = async (): Promise<string[]> => {
    const { data } = await api.get('/ws/agents')
    return data
}

// ============= Client Device Config =============
export const getClientDeviceConfig = async (id: number): Promise<string> => {
    const { data } = await api.get(`/client/devices/${id}/config`)
    return data.config || data
}

// ============= User Group Management =============
export const addUserToGroup = async (userId: string, groupName: string): Promise<void> => {
    await api.post(`/access/users/${userId}/groups`, { group_name: groupName })
}

export const removeUserFromGroup = async (userId: string, groupName: string): Promise<void> => {
    await api.delete(`/access/users/${userId}/groups/${groupName}`)
}

// ============= Events =============
export const getEvents = async (limit?: number): Promise<EventStoreEntry[]> => {
    const { data } = await api.get('/admin/events', { params: { limit: limit || 100 } })
    return data
}

export default api
