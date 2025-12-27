import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
    Activity,
    Search,

    Clock,
    Server,
    Smartphone,
    Shield,
    Users,
    AlertTriangle,
    CheckCircle,
    XCircle,
    ChevronDown,
    RefreshCw
} from 'lucide-react'
import { getEvents } from '@/lib/api'
import type { EventStoreEntry } from '@/types'

const EVENT_ICONS: Record<string, React.ReactNode> = {
    'node.registered': <Server className="w-4 h-4" />,
    'node.approved': <CheckCircle className="w-4 h-4" />,
    'node.suspended': <AlertTriangle className="w-4 h-4" />,
    'node.revoked': <XCircle className="w-4 h-4" />,
    'node.heartbeat': <Activity className="w-4 h-4" />,
    'client.created': <Smartphone className="w-4 h-4" />,
    'client.revoked': <XCircle className="w-4 h-4" />,
    'user.created': <Users className="w-4 h-4" />,
    'user.deleted': <Users className="w-4 h-4" />,
    'group.created': <Users className="w-4 h-4" />,
    'policy.created': <Shield className="w-4 h-4" />,
    'policy.deleted': <Shield className="w-4 h-4" />,
    'trust.score_updated': <Shield className="w-4 h-4" />,
}

const EVENT_COLORS: Record<string, string> = {
    'node.registered': 'text-blue-400 bg-blue-500/10',
    'node.approved': 'text-green-400 bg-green-500/10',
    'node.suspended': 'text-yellow-400 bg-yellow-500/10',
    'node.revoked': 'text-red-400 bg-red-500/10',
    'node.heartbeat': 'text-slate-400 bg-slate-500/10',
    'client.created': 'text-pink-400 bg-pink-500/10',
    'client.revoked': 'text-red-400 bg-red-500/10',
    'user.created': 'text-purple-400 bg-purple-500/10',
    'user.deleted': 'text-red-400 bg-red-500/10',
    'group.created': 'text-indigo-400 bg-indigo-500/10',
    'policy.created': 'text-cyan-400 bg-cyan-500/10',
    'policy.deleted': 'text-red-400 bg-red-500/10',
    'trust.score_updated': 'text-amber-400 bg-amber-500/10',
}

function formatDate(timestamp: string): string {
    const date = new Date(timestamp)
    return date.toLocaleString()
}

function formatRelativeTime(timestamp: string): string {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`
    return date.toLocaleDateString()
}

function EventCard({ event, expanded, onToggle }: { event: EventStoreEntry; expanded: boolean; onToggle: () => void }) {
    const icon = EVENT_ICONS[event.event_type] || <Activity className="w-4 h-4" />
    const colorClass = EVENT_COLORS[event.event_type] || 'text-slate-400 bg-slate-500/10'

    return (
        <div className="card hover:border-slate-700 transition-colors overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full p-4 text-left flex items-start gap-4"
            >
                <div className={`p-2 rounded-lg ${colorClass}`}>
                    {icon}
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                        <div>
                            <p className="text-white font-medium">{event.event_type}</p>
                            <p className="text-slate-500 text-sm mt-0.5">
                                {event.aggregate_type} #{event.aggregate_id}
                            </p>
                        </div>
                        <div className="flex items-center gap-2 text-slate-500 text-sm flex-shrink-0">
                            <Clock className="w-3.5 h-3.5" />
                            <span title={formatDate(event.timestamp)}>{formatRelativeTime(event.timestamp)}</span>
                            <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
                        </div>
                    </div>
                </div>
            </button>

            {expanded && (
                <div className="px-4 pb-4 border-t border-slate-800 pt-4 ml-14">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span className="text-slate-500">Event ID</span>
                            <p className="text-white font-mono mt-0.5">{event.id}</p>
                        </div>
                        <div>
                            <span className="text-slate-500">Version</span>
                            <p className="text-white mt-0.5">{event.version}</p>
                        </div>
                        <div>
                            <span className="text-slate-500">Timestamp</span>
                            <p className="text-white mt-0.5">{formatDate(event.timestamp)}</p>
                        </div>
                        <div>
                            <span className="text-slate-500">Aggregate</span>
                            <p className="text-white mt-0.5">{event.aggregate_type}</p>
                        </div>
                    </div>
                    {event.data && Object.keys(event.data).length > 0 && (
                        <div className="mt-4">
                            <span className="text-slate-500 text-sm">Event Data</span>
                            <pre className="mt-1 p-3 bg-slate-950 rounded-lg text-xs text-slate-300 font-mono overflow-x-auto">
                                {JSON.stringify(event.data, null, 2)}
                            </pre>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default function EventsPage() {
    const [search, setSearch] = useState('')
    const [typeFilter, setTypeFilter] = useState<string>('all')
    const [expandedId, setExpandedId] = useState<number | null>(null)

    const { data: events = [], isLoading, refetch, isFetching } = useQuery({
        queryKey: ['events'],
        queryFn: () => getEvents(100),
        refetchInterval: 10000, // Refresh every 10s
    })

    // Get unique event types for filter
    const eventTypes = [...new Set(events.map(e => e.event_type))].sort()

    // Filter events
    const filteredEvents = events.filter((event) => {
        const matchesSearch =
            event.event_type.toLowerCase().includes(search.toLowerCase()) ||
            event.aggregate_type.toLowerCase().includes(search.toLowerCase()) ||
            event.aggregate_id.toString().includes(search)
        const matchesType = typeFilter === 'all' || event.event_type === typeFilter
        return matchesSearch && matchesType
    })

    // Group events by date
    const groupedEvents = filteredEvents.reduce((acc, event) => {
        const date = new Date(event.timestamp).toLocaleDateString()
        if (!acc[date]) acc[date] = []
        acc[date].push(event)
        return acc
    }, {} as Record<string, EventStoreEntry[]>)

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Event Log</h1>
                    <p className="text-slate-400 mt-1">System events and audit trail</p>
                </div>
                <button
                    onClick={() => refetch()}
                    className="btn btn-secondary gap-2"
                    disabled={isFetching}
                >
                    <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="card p-4">
                    <p className="text-2xl font-bold text-white">{events.length}</p>
                    <p className="text-slate-400 text-sm">Total Events</p>
                </div>
                <div className="card p-4">
                    <p className="text-2xl font-bold text-white">{eventTypes.length}</p>
                    <p className="text-slate-400 text-sm">Event Types</p>
                </div>
                <div className="card p-4">
                    <p className="text-2xl font-bold text-white">
                        {events.filter(e => e.event_type.includes('node.')).length}
                    </p>
                    <p className="text-slate-400 text-sm">Node Events</p>
                </div>
                <div className="card p-4">
                    <p className="text-2xl font-bold text-white">
                        {events.filter(e => {
                            const date = new Date(e.timestamp)
                            const today = new Date()
                            return date.toDateString() === today.toDateString()
                        }).length}
                    </p>
                    <p className="text-slate-400 text-sm">Today</p>
                </div>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-4">
                <div className="flex-1 min-w-[200px] relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search events..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                    />
                </div>
                <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                >
                    <option value="all">All Types</option>
                    {eventTypes.map((type) => (
                        <option key={type} value={type}>{type}</option>
                    ))}
                </select>
            </div>

            {/* Events Timeline */}
            {isLoading ? (
                <div className="space-y-3">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="card p-4 animate-pulse">
                            <div className="flex items-start gap-4">
                                <div className="w-10 h-10 bg-slate-800 rounded-lg" />
                                <div className="flex-1">
                                    <div className="h-4 bg-slate-800 rounded w-32" />
                                    <div className="h-3 bg-slate-800 rounded w-24 mt-2" />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : filteredEvents.length === 0 ? (
                <div className="card p-12 text-center">
                    <Activity className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p className="text-slate-400">No events found</p>
                </div>
            ) : (
                <div className="space-y-6">
                    {Object.entries(groupedEvents).map(([date, dayEvents]) => (
                        <div key={date}>
                            <div className="flex items-center gap-4 mb-3">
                                <div className="text-sm font-medium text-slate-400">{date}</div>
                                <div className="flex-1 h-px bg-slate-800" />
                                <div className="text-xs text-slate-500">{dayEvents.length} events</div>
                            </div>
                            <div className="space-y-2">
                                {dayEvents.map((event) => (
                                    <EventCard
                                        key={event.id}
                                        event={event}
                                        expanded={expandedId === event.id}
                                        onToggle={() => setExpandedId(expandedId === event.id ? null : event.id)}
                                    />
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Summary */}
            <div className="flex items-center gap-4 text-sm text-slate-500">
                <span>Showing: {filteredEvents.length} of {events.length} events</span>
            </div>
        </div>
    )
}
