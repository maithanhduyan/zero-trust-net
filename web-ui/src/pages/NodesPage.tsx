import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    Server,
    Search,
    CheckCircle,
    XCircle,
    Clock,
    AlertTriangle,
    MoreVertical,

    Wifi,
    WifiOff
} from 'lucide-react'
import { getNodes, approveNode, suspendNode, revokeNode } from '@/lib/api'
import type { Node } from '@/types'

function formatDate(dateString?: string): string {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return date.toLocaleDateString()
}

function StatusBadge({ status }: { status: string }) {
    const config: Record<string, { icon: React.ReactNode; class: string }> = {
        active: { icon: <CheckCircle className="w-3.5 h-3.5" />, class: 'badge-success' },
        pending: { icon: <Clock className="w-3.5 h-3.5" />, class: 'badge-warning' },
        suspended: { icon: <AlertTriangle className="w-3.5 h-3.5" />, class: 'badge-warning' },
        revoked: { icon: <XCircle className="w-3.5 h-3.5" />, class: 'badge-danger' },
    }
    const { icon, class: className } = config[status] || { icon: null, class: 'badge-neutral' }

    return (
        <span className={`badge ${className} gap-1`}>
            {icon}
            {status}
        </span>
    )
}

function RoleBadge({ role }: { role: string }) {
    const colors: Record<string, string> = {
        hub: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
        app: 'bg-green-500/10 text-green-400 border-green-500/30',
        database: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
        ops: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    }

    return (
        <span className={`px-2 py-0.5 rounded border text-xs font-medium capitalize ${colors[role] || 'bg-slate-500/10 text-slate-400 border-slate-500/30'}`}>
            {role}
        </span>
    )
}

function TrustScoreBar({ score }: { score: number }) {
    const color = score >= 0.7 ? 'bg-green-500' : score >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'

    return (
        <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full ${color}`} style={{ width: `${score * 100}%` }} />
            </div>
            <span className="text-xs text-slate-400 w-8">{(score * 100).toFixed(0)}%</span>
        </div>
    )
}

export default function NodesPage() {
    const queryClient = useQueryClient()
    const [search, setSearch] = useState('')
    const [statusFilter, setStatusFilter] = useState<string>('all')
    const [roleFilter, setRoleFilter] = useState<string>('all')
    const [openMenu, setOpenMenu] = useState<number | null>(null)

    const { data: nodes = [], isLoading } = useQuery({
        queryKey: ['nodes'],
        queryFn: getNodes,
    })

    const approveMutation = useMutation({
        mutationFn: approveNode,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nodes'] }),
    })

    const suspendMutation = useMutation({
        mutationFn: suspendNode,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nodes'] }),
    })

    const revokeMutation = useMutation({
        mutationFn: revokeNode,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nodes'] }),
    })

    // Filter nodes
    const filteredNodes = nodes.filter((node) => {
        const matchesSearch = node.hostname.toLowerCase().includes(search.toLowerCase()) ||
            node.overlay_ip?.includes(search) ||
            node.real_ip?.includes(search)
        const matchesStatus = statusFilter === 'all' || node.status === statusFilter
        const matchesRole = roleFilter === 'all' || node.role === roleFilter
        return matchesSearch && matchesStatus && matchesRole
    })

    const handleAction = (action: string, node: Node) => {
        setOpenMenu(null)
        switch (action) {
            case 'approve':
                approveMutation.mutate(node.id)
                break
            case 'suspend':
                suspendMutation.mutate(node.id)
                break
            case 'revoke':
                revokeMutation.mutate(node.id)
                break
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-white">Nodes</h1>
                <p className="text-slate-400 mt-1">Manage network infrastructure nodes</p>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-4">
                <div className="flex-1 min-w-[200px] relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search by hostname, IP..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                    />
                </div>
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                >
                    <option value="all">All Status</option>
                    <option value="active">Active</option>
                    <option value="pending">Pending</option>
                    <option value="suspended">Suspended</option>
                    <option value="revoked">Revoked</option>
                </select>
                <select
                    value={roleFilter}
                    onChange={(e) => setRoleFilter(e.target.value)}
                    className="px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                >
                    <option value="all">All Roles</option>
                    <option value="hub">Hub</option>
                    <option value="app">App</option>
                    <option value="database">Database</option>
                    <option value="ops">Ops</option>
                </select>
            </div>

            {/* Nodes Table */}
            <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-slate-800">
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Node
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Status
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Role
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Trust Score
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Last Seen
                                </th>
                                <th className="px-6 py-4 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {isLoading ? (
                                [...Array(5)].map((_, i) => (
                                    <tr key={i} className="animate-pulse">
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-32" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-16" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-16" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-24" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-16" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-8 ml-auto" /></td>
                                    </tr>
                                ))
                            ) : filteredNodes.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                                        <Server className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                        <p>No nodes found</p>
                                    </td>
                                </tr>
                            ) : (
                                filteredNodes.map((node) => (
                                    <tr key={node.id} className="hover:bg-slate-900/50 transition-colors">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="p-2 bg-blue-500/10 rounded-lg">
                                                    <Server className="w-5 h-5 text-blue-400" />
                                                </div>
                                                <div>
                                                    <p className="text-white font-medium">{node.hostname}</p>
                                                    <p className="text-slate-500 text-sm font-mono">{node.overlay_ip}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <StatusBadge status={node.status} />
                                        </td>
                                        <td className="px-6 py-4">
                                            <RoleBadge role={node.role} />
                                        </td>
                                        <td className="px-6 py-4 min-w-[140px]">
                                            <TrustScoreBar score={node.trust_score} />
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-1.5 text-sm text-slate-400">
                                                {node.last_seen ? (
                                                    <>
                                                        <Wifi className="w-3 h-3 text-green-400" />
                                                        {formatDate(node.last_seen)}
                                                    </>
                                                ) : (
                                                    <>
                                                        <WifiOff className="w-3 h-3 text-slate-500" />
                                                        Never
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="relative">
                                                <button
                                                    onClick={() => setOpenMenu(openMenu === node.id ? null : node.id)}
                                                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                                                >
                                                    <MoreVertical className="w-4 h-4" />
                                                </button>
                                                {openMenu === node.id && (
                                                    <div className="absolute right-0 mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-10 min-w-[120px]">
                                                        {node.status === 'pending' && (
                                                            <button
                                                                onClick={() => handleAction('approve', node)}
                                                                className="w-full px-4 py-2 text-left text-sm text-green-400 hover:bg-slate-800"
                                                            >
                                                                Approve
                                                            </button>
                                                        )}
                                                        {node.status === 'active' && (
                                                            <button
                                                                onClick={() => handleAction('suspend', node)}
                                                                className="w-full px-4 py-2 text-left text-sm text-yellow-400 hover:bg-slate-800"
                                                            >
                                                                Suspend
                                                            </button>
                                                        )}
                                                        {node.status !== 'revoked' && (
                                                            <button
                                                                onClick={() => handleAction('revoke', node)}
                                                                className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-slate-800"
                                                            >
                                                                Revoke
                                                            </button>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Summary */}
            <div className="flex items-center gap-4 text-sm text-slate-500">
                <span>Total: {nodes.length} nodes</span>
                <span>•</span>
                <span>Showing: {filteredNodes.length}</span>
            </div>
        </div>
    )
}
