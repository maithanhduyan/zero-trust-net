import { Server, Smartphone, Users, Shield, TrendingUp, CheckCircle, Clock, AlertTriangle } from 'lucide-react'
import type { Node, ClientDevice, User } from '@/types'

interface MetricsCardsProps {
    nodes: Node[]
    clients: ClientDevice[]
    users?: User[]
    isLoading?: boolean
}

interface MetricCardProps {
    title: string
    value: string | number
    subtitle?: string
    icon: React.ReactNode
    trend?: {
        value: number
        isPositive: boolean
    }
    color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'pink'
}

function MetricCard({ title, value, subtitle, icon, trend, color = 'blue' }: MetricCardProps) {
    const colorStyles = {
        blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        green: 'bg-green-500/10 text-green-400 border-green-500/20',
        yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
        red: 'bg-red-500/10 text-red-400 border-red-500/20',
        purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
        pink: 'bg-pink-500/10 text-pink-400 border-pink-500/20',
    }

    return (
        <div className="card p-4">
            <div className="flex items-start justify-between">
                <div className={`p-2.5 rounded-lg border ${colorStyles[color]}`}>
                    {icon}
                </div>
                {trend && (
                    <div className={`flex items-center gap-1 text-sm ${trend.isPositive ? 'text-green-400' : 'text-red-400'}`}>
                        <TrendingUp className={`w-4 h-4 ${!trend.isPositive && 'rotate-180'}`} />
                        <span>{trend.value}%</span>
                    </div>
                )}
            </div>
            <div className="mt-4">
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-slate-400 text-sm mt-1">{title}</p>
                {subtitle && <p className="text-slate-500 text-xs mt-0.5">{subtitle}</p>}
            </div>
        </div>
    )
}

function LoadingCard() {
    return (
        <div className="card p-4 animate-pulse">
            <div className="flex items-start justify-between">
                <div className="w-10 h-10 bg-slate-800 rounded-lg" />
            </div>
            <div className="mt-4">
                <div className="h-8 bg-slate-800 rounded w-16" />
                <div className="h-4 bg-slate-800 rounded w-24 mt-2" />
            </div>
        </div>
    )
}

export default function MetricsCards({
    nodes,
    clients,
    users = [],
    isLoading = false,
}: MetricsCardsProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[...Array(4)].map((_, i) => (
                    <LoadingCard key={i} />
                ))}
            </div>
        )
    }

    // Calculate node metrics
    const activeNodes = nodes.filter((n) => n.status === 'active').length
    const pendingNodes = nodes.filter((n) => n.status === 'pending').length
    const hubNodes = nodes.filter((n) => n.role === 'hub')
    const avgTrustScore = nodes.length > 0
        ? nodes.reduce((sum, n) => sum + n.trust_score, 0) / nodes.length
        : 0

    // Calculate client metrics
    const activeClients = clients.filter((c) => c.status === 'active').length

    // High risk nodes
    const highRiskNodes = nodes.filter((n) =>
        n.risk_level === 'high' || n.risk_level === 'critical'
    ).length

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
                title="Total Nodes"
                value={nodes.length}
                subtitle={`${activeNodes} active, ${pendingNodes} pending`}
                icon={<Server className="w-5 h-5" />}
                color="blue"
            />
            <MetricCard
                title="Client Devices"
                value={clients.length}
                subtitle={`${activeClients} connected`}
                icon={<Smartphone className="w-5 h-5" />}
                color="pink"
            />
            <MetricCard
                title="Average Trust Score"
                value={`${(avgTrustScore * 100).toFixed(0)}%`}
                subtitle={highRiskNodes > 0 ? `${highRiskNodes} high risk` : 'All nodes healthy'}
                icon={<Shield className="w-5 h-5" />}
                color={avgTrustScore >= 0.7 ? 'green' : avgTrustScore >= 0.4 ? 'yellow' : 'red'}
            />
            <MetricCard
                title="Users"
                value={users.length}
                subtitle={hubNodes.length > 0 ? `${hubNodes.length} hub(s) online` : 'No hubs'}
                icon={<Users className="w-5 h-5" />}
                color="purple"
            />
        </div>
    )
}

// Additional detailed metrics component
export function DetailedMetrics({
    nodes,
    clients,
}: {
    nodes: Node[]
    clients: ClientDevice[]
}) {
    const metrics = [
        {
            label: 'Active',
            nodes: nodes.filter((n) => n.status === 'active').length,
            clients: clients.filter((c) => c.status === 'active').length,
            icon: <CheckCircle className="w-4 h-4 text-green-400" />,
        },
        {
            label: 'Pending',
            nodes: nodes.filter((n) => n.status === 'pending').length,
            clients: clients.filter((c) => c.status === 'pending').length,
            icon: <Clock className="w-4 h-4 text-yellow-400" />,
        },
        {
            label: 'Suspended',
            nodes: nodes.filter((n) => n.status === 'suspended').length,
            clients: clients.filter((c) => c.status === 'suspended').length,
            icon: <AlertTriangle className="w-4 h-4 text-orange-400" />,
        },
    ]

    return (
        <div className="card p-4">
            <h3 className="text-sm font-medium text-slate-400 mb-4">Status Breakdown</h3>
            <div className="space-y-3">
                {metrics.map((m) => (
                    <div key={m.label} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            {m.icon}
                            <span className="text-white">{m.label}</span>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                            <span className="text-slate-400">
                                <Server className="w-3 h-3 inline mr-1" />
                                {m.nodes}
                            </span>
                            <span className="text-slate-400">
                                <Smartphone className="w-3 h-3 inline mr-1" />
                                {m.clients}
                            </span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}

// Role distribution component
export function RoleDistribution({ nodes }: { nodes: Node[] }) {
    const roles = ['hub', 'app', 'database', 'ops'] as const
    const roleColors = {
        hub: 'bg-blue-500',
        app: 'bg-green-500',
        database: 'bg-orange-500',
        ops: 'bg-purple-500',
    }

    const total = nodes.length || 1

    return (
        <div className="card p-4">
            <h3 className="text-sm font-medium text-slate-400 mb-4">Node Roles</h3>
            <div className="flex h-2 rounded-full overflow-hidden bg-slate-800 mb-4">
                {roles.map((role) => {
                    const count = nodes.filter((n) => n.role === role).length
                    const width = (count / total) * 100
                    return (
                        <div
                            key={role}
                            className={`${roleColors[role]} transition-all`}
                            style={{ width: `${width}%` }}
                        />
                    )
                })}
            </div>
            <div className="grid grid-cols-2 gap-2">
                {roles.map((role) => {
                    const count = nodes.filter((n) => n.role === role).length
                    return (
                        <div key={role} className="flex items-center gap-2 text-sm">
                            <div className={`w-3 h-3 rounded-full ${roleColors[role]}`} />
                            <span className="text-slate-400 capitalize">{role}</span>
                            <span className="text-white ml-auto">{count}</span>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
