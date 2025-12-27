import { X, Server, Smartphone, Clock, Shield, Activity, Wifi, WifiOff } from 'lucide-react'
import type { Node, ClientDevice } from '@/types'

interface NodeDetailsPanelProps {
    node: Node | ClientDevice | null
    nodeType?: 'node' | 'client'
    onClose: () => void
    onAction?: (action: string, id: number) => void
}

function isNode(item: Node | ClientDevice): item is Node {
    return 'hostname' in item
}

function formatDate(dateString?: string): string {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    return date.toLocaleString()
}

function getStatusBadge(status: string) {
    const styles: Record<string, string> = {
        active: 'badge-success',
        pending: 'badge-warning',
        suspended: 'badge-warning',
        revoked: 'badge-danger',
    }
    return styles[status] || 'badge-neutral'
}

function getRiskBadge(riskLevel: string) {
    const styles: Record<string, string> = {
        low: 'badge-success',
        medium: 'badge-warning',
        high: 'badge-danger',
        critical: 'badge-danger',
    }
    return styles[riskLevel] || 'badge-neutral'
}

export default function NodeDetailsPanel({
    node,
    onClose,
    onAction,
}: NodeDetailsPanelProps) {
    if (!node) return null

    const isNodeType = isNode(node)

    return (
        <div className="fixed inset-y-0 right-0 w-96 bg-slate-900 border-l border-slate-800 shadow-xl z-50 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
                <div className="flex items-center gap-3">
                    {isNodeType ? (
                        <Server className="w-5 h-5 text-blue-400" />
                    ) : (
                        <Smartphone className="w-5 h-5 text-pink-400" />
                    )}
                    <h2 className="text-lg font-semibold text-white">
                        {isNodeType ? node.hostname : node.device_name}
                    </h2>
                </div>
                <button
                    onClick={onClose}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6">
                {/* Status */}
                <div className="flex items-center justify-between">
                    <span className="text-slate-400">Status</span>
                    <span className={`badge ${getStatusBadge(node.status)}`}>
                        {node.status}
                    </span>
                </div>

                {isNodeType ? (
                    <>
                        {/* Node Details */}
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <span className="text-slate-400">Role</span>
                                <span className="text-white capitalize">{node.role}</span>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="text-slate-400">Overlay IP</span>
                                <span className="text-white font-mono text-sm">{node.overlay_ip}</span>
                            </div>

                            {node.real_ip && (
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Public IP</span>
                                    <span className="text-white font-mono text-sm">{node.real_ip}</span>
                                </div>
                            )}

                            {/* Trust Score */}
                            <div className="pt-4 border-t border-slate-800">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-slate-400 flex items-center gap-2">
                                        <Shield className="w-4 h-4" />
                                        Trust Score
                                    </span>
                                    <span className="text-white font-semibold">
                                        {(node.trust_score * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full transition-all ${node.trust_score >= 0.7
                                            ? 'bg-green-500'
                                            : node.trust_score >= 0.4
                                                ? 'bg-yellow-500'
                                                : 'bg-red-500'
                                            }`}
                                        style={{ width: `${node.trust_score * 100}%` }}
                                    />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <span className="text-slate-400 text-xs">Risk Level</span>
                                    <span className={`badge ${getRiskBadge(node.risk_level)}`}>
                                        {node.risk_level}
                                    </span>
                                </div>
                            </div>

                            {/* Connection Status */}
                            <div className="pt-4 border-t border-slate-800">
                                <div className="flex items-center gap-2 mb-2">
                                    <Activity className="w-4 h-4 text-slate-400" />
                                    <span className="text-slate-400">Connection</span>
                                </div>
                                <div className="space-y-2 text-sm">
                                    <div className="flex items-center justify-between">
                                        <span className="text-slate-500">Last Seen</span>
                                        <span className="text-white flex items-center gap-1">
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
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-slate-500">Agent Version</span>
                                        <span className="text-white">{node.agent_version || 'Unknown'}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-slate-500">OS</span>
                                        <span className="text-white truncate max-w-[150px]" title={node.os_info}>
                                            {node.os_info || 'Unknown'}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Timestamps */}
                            <div className="pt-4 border-t border-slate-800 text-sm">
                                <div className="flex items-center gap-2 mb-2">
                                    <Clock className="w-4 h-4 text-slate-400" />
                                    <span className="text-slate-400">Timestamps</span>
                                </div>
                                <div className="space-y-1 text-slate-500">
                                    <div>Created: {formatDate(node.created_at)}</div>
                                    <div>Updated: {formatDate(node.updated_at)}</div>
                                </div>
                            </div>
                        </div>
                    </>
                ) : (
                    <>
                        {/* Client Device Details */}
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <span className="text-slate-400">Device Type</span>
                                <span className="text-white capitalize">{node.device_type}</span>
                            </div>

                            {node.user_id && (
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Owner</span>
                                    <span className="text-white">{node.user_id}</span>
                                </div>
                            )}

                            <div className="flex items-center justify-between">
                                <span className="text-slate-400">Overlay IP</span>
                                <span className="text-white font-mono text-sm">{node.overlay_ip}</span>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="text-slate-400">Tunnel Mode</span>
                                <span className="text-white capitalize">{node.tunnel_mode}</span>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="text-slate-400">Config Downloaded</span>
                                <span className={node.config_downloaded ? 'text-green-400' : 'text-slate-500'}>
                                    {node.config_downloaded ? 'Yes' : 'No'}
                                </span>
                            </div>

                            {/* Expiration */}
                            <div className="pt-4 border-t border-slate-800">
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Expires</span>
                                    <span className="text-white">{formatDate(node.expires_at)}</span>
                                </div>
                            </div>
                        </div>
                    </>
                )}

                {/* Actions */}
                <div className="pt-4 border-t border-slate-800 space-y-2">
                    {node.status === 'pending' && (
                        <button
                            onClick={() => onAction?.('approve', node.id)}
                            className="btn btn-success w-full justify-center"
                        >
                            Approve
                        </button>
                    )}
                    {node.status === 'active' && (
                        <button
                            onClick={() => onAction?.('suspend', node.id)}
                            className="btn btn-warning w-full justify-center"
                        >
                            Suspend
                        </button>
                    )}
                    {node.status !== 'revoked' && (
                        <button
                            onClick={() => onAction?.('revoke', node.id)}
                            className="btn btn-danger w-full justify-center"
                        >
                            Revoke
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}
