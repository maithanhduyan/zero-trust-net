import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    Shield,
    Search,
    Plus,
    MoreVertical,
    Trash2,
    CheckCircle,
    XCircle,
    ChevronRight,
    Server,
    Users
} from 'lucide-react'
import { getPolicies, getUserAccessPolicies, createPolicy, deletePolicy, createUserAccessPolicy, deleteUserAccessPolicy } from '@/lib/api'
import type { PolicyAction, AccessAction } from '@/types'

function ActionBadge({ action }: { action: PolicyAction | AccessAction }) {
    const config: Record<string, { class: string }> = {
        allow: { class: 'badge-success' },
        deny: { class: 'badge-danger' },
        require_mfa: { class: 'badge-warning' },
    }
    return (
        <span className={`badge ${config[action]?.class || 'badge-neutral'}`}>
            {action === 'allow' && <CheckCircle className="w-3 h-3 mr-1" />}
            {action === 'deny' && <XCircle className="w-3 h-3 mr-1" />}
            {action}
        </span>
    )
}

function CreateAccessPolicyModal({
    isOpen,
    onClose,
    onCreate
}: {
    isOpen: boolean
    onClose: () => void
    onCreate: (data: { name: string; source_role: string; target_role: string; action: PolicyAction; ports?: number[] }) => void
}) {
    const [name, setName] = useState('')
    const [sourceRole, setSourceRole] = useState('app')
    const [targetRole, setTargetRole] = useState('database')
    const [action, setAction] = useState<PolicyAction>('allow')
    const [ports, setPorts] = useState('')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        const portList = ports ? ports.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p)) : undefined
        onCreate({
            name,
            source_role: sourceRole,
            target_role: targetRole,
            action,
            ports: portList && portList.length > 0 ? portList : undefined,
        })
        setName('')
        setPorts('')
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-md shadow-xl">
                <div className="p-6 border-b border-slate-800">
                    <h2 className="text-lg font-semibold text-white">Create Access Policy</h2>
                    <p className="text-slate-400 text-sm mt-1">Define access rules between node roles</p>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Policy Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g., app-to-db-access"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">Source Role</label>
                            <select
                                value={sourceRole}
                                onChange={(e) => setSourceRole(e.target.value)}
                                className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                            >
                                <option value="hub">Hub</option>
                                <option value="app">App</option>
                                <option value="database">Database</option>
                                <option value="ops">Ops</option>
                                <option value="*">Any (*)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">Target Role</label>
                            <select
                                value={targetRole}
                                onChange={(e) => setTargetRole(e.target.value)}
                                className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                            >
                                <option value="hub">Hub</option>
                                <option value="app">App</option>
                                <option value="database">Database</option>
                                <option value="ops">Ops</option>
                                <option value="*">Any (*)</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Action</label>
                        <select
                            value={action}
                            onChange={(e) => setAction(e.target.value as PolicyAction)}
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="allow">Allow</option>
                            <option value="deny">Deny</option>
                            <option value="require_mfa">Require MFA</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Ports (optional)</label>
                        <input
                            type="text"
                            value={ports}
                            onChange={(e) => setPorts(e.target.value)}
                            placeholder="e.g., 80, 443, 5432"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                        />
                    </div>

                    <div className="flex gap-3 pt-4">
                        <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary flex-1">
                            Create Policy
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

function CreateUserPolicyModal({
    isOpen,
    onClose,
    onCreate
}: {
    isOpen: boolean
    onClose: () => void
    onCreate: (data: { user_id: number; target_resource: string; action: AccessAction }) => void
}) {
    const [userId, setUserId] = useState('')
    const [targetResource, setTargetResource] = useState('')
    const [action, setAction] = useState<AccessAction>('allow')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onCreate({
            user_id: parseInt(userId),
            target_resource: targetResource,
            action,
        })
        setUserId('')
        setTargetResource('')
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-md shadow-xl">
                <div className="p-6 border-b border-slate-800">
                    <h2 className="text-lg font-semibold text-white">Create User Access Policy</h2>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">User ID</label>
                        <input
                            type="number"
                            value={userId}
                            onChange={(e) => setUserId(e.target.value)}
                            placeholder="Enter user ID"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Target Resource</label>
                        <input
                            type="text"
                            value={targetResource}
                            onChange={(e) => setTargetResource(e.target.value)}
                            placeholder="e.g., database:*, api:read"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Action</label>
                        <select
                            value={action}
                            onChange={(e) => setAction(e.target.value as AccessAction)}
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="allow">Allow</option>
                            <option value="deny">Deny</option>
                        </select>
                    </div>
                    <div className="flex gap-3 pt-4">
                        <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary flex-1">
                            Create Policy
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export default function PoliciesPage() {
    const queryClient = useQueryClient()
    const [activeTab, setActiveTab] = useState<'access' | 'user'>('access')
    const [search, setSearch] = useState('')
    const [showCreateAccessModal, setShowCreateAccessModal] = useState(false)
    const [showCreateUserModal, setShowCreateUserModal] = useState(false)
    const [openMenu, setOpenMenu] = useState<number | null>(null)

    const { data: accessPolicies = [], isLoading: accessLoading } = useQuery({
        queryKey: ['policies'],
        queryFn: getPolicies,
    })

    const { data: userPolicies = [], isLoading: userLoading } = useQuery({
        queryKey: ['userPolicies'],
        queryFn: getUserAccessPolicies,
    })

    const createPolicyMutation = useMutation({
        mutationFn: createPolicy,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['policies'] }),
    })

    const deletePolicyMutation = useMutation({
        mutationFn: deletePolicy,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['policies'] }),
    })

    const createUserPolicyMutation = useMutation({
        mutationFn: createUserAccessPolicy,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['userPolicies'] }),
    })

    const deleteUserPolicyMutation = useMutation({
        mutationFn: deleteUserAccessPolicy,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['userPolicies'] }),
    })

    const filteredAccessPolicies = accessPolicies.filter((p) =>
        p.name.toLowerCase().includes(search.toLowerCase())
    )

    const filteredUserPolicies = userPolicies.filter((p) =>
        p.target_resource.toLowerCase().includes(search.toLowerCase())
    )

    const isLoading = activeTab === 'access' ? accessLoading : userLoading

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Policies</h1>
                    <p className="text-slate-400 mt-1">Manage access control policies</p>
                </div>
                <button
                    onClick={() => activeTab === 'access' ? setShowCreateAccessModal(true) : setShowCreateUserModal(true)}
                    className="btn btn-primary gap-2"
                >
                    <Plus className="w-4 h-4" />
                    Add Policy
                </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 bg-slate-900 p-1 rounded-lg w-fit">
                <button
                    onClick={() => setActiveTab('access')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'access'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-400 hover:text-white'
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <Server className="w-4 h-4" />
                        Node Access ({accessPolicies.length})
                    </span>
                </button>
                <button
                    onClick={() => setActiveTab('user')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'user'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-400 hover:text-white'
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        User Access ({userPolicies.length})
                    </span>
                </button>
            </div>

            {/* Search */}
            <div className="relative max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                    type="text"
                    placeholder="Search policies..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
            </div>

            {/* Access Policies */}
            {activeTab === 'access' && (
                <div className="space-y-3">
                    {isLoading ? (
                        [...Array(4)].map((_, i) => (
                            <div key={i} className="card p-4 animate-pulse">
                                <div className="h-5 bg-slate-800 rounded w-32" />
                                <div className="h-4 bg-slate-800 rounded w-64 mt-2" />
                            </div>
                        ))
                    ) : filteredAccessPolicies.length === 0 ? (
                        <div className="card p-12 text-center">
                            <Shield className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                            <p className="text-slate-400">No access policies found</p>
                        </div>
                    ) : (
                        filteredAccessPolicies.map((policy) => (
                            <div key={policy.id} className="card p-4 hover:border-slate-700 transition-colors">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                                            <Shield className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <p className="text-white font-medium">{policy.name}</p>
                                            <div className="flex items-center gap-2 mt-1 text-sm text-slate-400">
                                                <span className="px-2 py-0.5 bg-slate-800 rounded capitalize">{policy.source_role}</span>
                                                <ChevronRight className="w-4 h-4" />
                                                <span className="px-2 py-0.5 bg-slate-800 rounded capitalize">{policy.target_role}</span>
                                                {policy.ports && policy.ports.length > 0 && (
                                                    <span className="text-slate-500">
                                                        ports: {policy.ports.join(', ')}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <ActionBadge action={policy.action} />
                                        <div className="relative">
                                            <button
                                                onClick={() => setOpenMenu(openMenu === policy.id ? null : policy.id)}
                                                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                                            >
                                                <MoreVertical className="w-4 h-4" />
                                            </button>
                                            {openMenu === policy.id && (
                                                <div className="absolute right-0 mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-10">
                                                    <button
                                                        onClick={() => {
                                                            deletePolicyMutation.mutate(policy.id)
                                                            setOpenMenu(null)
                                                        }}
                                                        className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-slate-800 flex items-center gap-2"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                        Delete
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}

            {/* User Policies */}
            {activeTab === 'user' && (
                <div className="card overflow-hidden">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-slate-800">
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    User
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Resource
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Action
                                </th>
                                <th className="px-6 py-4 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {userLoading ? (
                                [...Array(3)].map((_, i) => (
                                    <tr key={i} className="animate-pulse">
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-24" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-32" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-16" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-8 ml-auto" /></td>
                                    </tr>
                                ))
                            ) : filteredUserPolicies.length === 0 ? (
                                <tr>
                                    <td colSpan={4} className="px-6 py-12 text-center text-slate-400">
                                        <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                        <p>No user policies found</p>
                                    </td>
                                </tr>
                            ) : (
                                filteredUserPolicies.map((policy) => (
                                    <tr key={policy.id} className="hover:bg-slate-900/50 transition-colors">
                                        <td className="px-6 py-4 text-white">
                                            User #{policy.user_id}
                                        </td>
                                        <td className="px-6 py-4">
                                            <code className="px-2 py-1 bg-slate-800 rounded text-sm text-slate-300">
                                                {policy.target_resource}
                                            </code>
                                        </td>
                                        <td className="px-6 py-4">
                                            <ActionBadge action={policy.action} />
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button
                                                onClick={() => deleteUserPolicyMutation.mutate(policy.id)}
                                                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-red-400"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Modals */}
            <CreateAccessPolicyModal
                isOpen={showCreateAccessModal}
                onClose={() => setShowCreateAccessModal(false)}
                onCreate={(data) => createPolicyMutation.mutate(data)}
            />
            <CreateUserPolicyModal
                isOpen={showCreateUserModal}
                onClose={() => setShowCreateUserModal(false)}
                onCreate={(data) => createUserPolicyMutation.mutate(data)}
            />
        </div>
    )
}
