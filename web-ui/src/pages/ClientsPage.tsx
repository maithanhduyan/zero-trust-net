import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    Smartphone,
    Search,
    Plus,
    QrCode,
    Download,
    MoreVertical,
    CheckCircle,
    Clock,
    XCircle,
    Laptop,
    Tablet,
    Monitor
} from 'lucide-react'
import { getClientDevices, createClientDevice, revokeClientDevice, getClientDeviceConfig } from '@/lib/api'
import type { ClientDevice, DeviceType, TunnelMode } from '@/types'

function DeviceIcon({ type }: { type: string }) {
    const icons: Record<string, React.ReactNode> = {
        laptop: <Laptop className="w-5 h-5" />,
        mobile: <Smartphone className="w-5 h-5" />,
        tablet: <Tablet className="w-5 h-5" />,
        desktop: <Monitor className="w-5 h-5" />,
    }
    return icons[type] || <Smartphone className="w-5 h-5" />
}

function StatusBadge({ status }: { status: string }) {
    const config: Record<string, { icon: React.ReactNode; class: string }> = {
        active: { icon: <CheckCircle className="w-3.5 h-3.5" />, class: 'badge-success' },
        pending: { icon: <Clock className="w-3.5 h-3.5" />, class: 'badge-warning' },
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

function CreateClientModal({
    isOpen,
    onClose,
    onCreate
}: {
    isOpen: boolean
    onClose: () => void
    onCreate: (data: { device_name: string; device_type: DeviceType; tunnel_mode: TunnelMode }) => void
}) {
    const [deviceName, setDeviceName] = useState('')
    const [deviceType, setDeviceType] = useState<DeviceType>('laptop')
    const [tunnelMode, setTunnelMode] = useState<TunnelMode>('split')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onCreate({
            device_name: deviceName,
            device_type: deviceType,
            tunnel_mode: tunnelMode,
        })
        setDeviceName('')
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-md shadow-xl">
                <div className="p-6 border-b border-slate-800">
                    <h2 className="text-lg font-semibold text-white">Add Client Device</h2>
                    <p className="text-slate-400 text-sm mt-1">Create a new client device configuration</p>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Device Name</label>
                        <input
                            type="text"
                            value={deviceName}
                            onChange={(e) => setDeviceName(e.target.value)}
                            placeholder="e.g., John's Laptop"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Device Type</label>
                        <select
                            value={deviceType}
                            onChange={(e) => setDeviceType(e.target.value as DeviceType)}
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="laptop">Laptop</option>
                            <option value="mobile">Mobile</option>
                            <option value="tablet">Tablet</option>
                            <option value="desktop">Desktop</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Tunnel Mode</label>
                        <select
                            value={tunnelMode}
                            onChange={(e) => setTunnelMode(e.target.value as TunnelMode)}
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="split">Split Tunnel (only network traffic)</option>
                            <option value="full">Full Tunnel (all traffic)</option>
                        </select>
                    </div>
                    <div className="flex gap-3 pt-4">
                        <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary flex-1">
                            Create Device
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

function ConfigModal({
    isOpen,
    onClose,
    config,
    deviceName
}: {
    isOpen: boolean
    onClose: () => void
    config: string | null
    deviceName: string
}) {
    if (!isOpen || !config) return null

    const downloadConfig = () => {
        const blob = new Blob([config], { type: 'text/plain' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${deviceName.replace(/\s+/g, '_')}.conf`
        a.click()
        URL.revokeObjectURL(url)
    }

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-2xl shadow-xl">
                <div className="p-6 border-b border-slate-800 flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-semibold text-white">WireGuard Configuration</h2>
                        <p className="text-slate-400 text-sm mt-1">{deviceName}</p>
                    </div>
                    <div className="flex gap-2">
                        <button onClick={downloadConfig} className="btn btn-primary gap-2">
                            <Download className="w-4 h-4" />
                            Download
                        </button>
                    </div>
                </div>
                <div className="p-6">
                    <pre className="bg-slate-950 border border-slate-800 rounded-lg p-4 text-sm text-slate-300 font-mono overflow-x-auto">
                        {config}
                    </pre>
                    <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                        <p className="text-sm text-blue-400">
                            <strong>Instructions:</strong> Import this configuration into your WireGuard client.
                            The config can only be downloaded once for security.
                        </p>
                    </div>
                </div>
                <div className="p-6 border-t border-slate-800">
                    <button onClick={onClose} className="btn btn-secondary w-full">
                        Close
                    </button>
                </div>
            </div>
        </div>
    )
}

export default function ClientsPage() {
    const queryClient = useQueryClient()
    const [search, setSearch] = useState('')
    const [statusFilter, setStatusFilter] = useState<string>('all')
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [openMenu, setOpenMenu] = useState<number | null>(null)
    const [configModal, setConfigModal] = useState<{ open: boolean; config: string | null; name: string }>({
        open: false,
        config: null,
        name: '',
    })

    const { data: clients = [], isLoading } = useQuery({
        queryKey: ['clients'],
        queryFn: getClientDevices,
    })

    const createMutation = useMutation({
        mutationFn: createClientDevice,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['clients'] })
        },
    })

    const revokeMutation = useMutation({
        mutationFn: revokeClientDevice,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['clients'] })
        },
    })

    const filteredClients = clients.filter((client) => {
        const matchesSearch = client.device_name.toLowerCase().includes(search.toLowerCase()) ||
            client.overlay_ip?.includes(search)
        const matchesStatus = statusFilter === 'all' || client.status === statusFilter
        return matchesSearch && matchesStatus
    })

    const handleCreate = (data: { device_name: string; device_type: DeviceType; tunnel_mode: TunnelMode }) => {
        createMutation.mutate(data)
    }

    const handleDownloadConfig = async (client: ClientDevice) => {
        try {
            const config = await getClientDeviceConfig(client.id)
            setConfigModal({ open: true, config, name: client.device_name })
        } catch (error) {
            console.error('Failed to get config:', error)
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Client Devices</h1>
                    <p className="text-slate-400 mt-1">Manage user devices and VPN access</p>
                </div>
                <button onClick={() => setShowCreateModal(true)} className="btn btn-primary gap-2">
                    <Plus className="w-4 h-4" />
                    Add Device
                </button>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-4">
                <div className="flex-1 min-w-[200px] relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search by device name, IP..."
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
                    <option value="revoked">Revoked</option>
                </select>
            </div>

            {/* Clients Grid */}
            {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="card p-4 animate-pulse">
                            <div className="flex items-start gap-3">
                                <div className="w-10 h-10 bg-slate-800 rounded-lg" />
                                <div className="flex-1">
                                    <div className="h-4 bg-slate-800 rounded w-24" />
                                    <div className="h-3 bg-slate-800 rounded w-32 mt-2" />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : filteredClients.length === 0 ? (
                <div className="card p-12 text-center">
                    <Smartphone className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p className="text-slate-400">No client devices found</p>
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="btn btn-primary mt-4 gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        Add First Device
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredClients.map((client) => (
                        <div key={client.id} className="card p-4 hover:border-slate-700 transition-colors">
                            <div className="flex items-start justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="p-2.5 bg-pink-500/10 rounded-lg text-pink-400">
                                        <DeviceIcon type={client.device_type} />
                                    </div>
                                    <div>
                                        <p className="text-white font-medium">{client.device_name}</p>
                                        <p className="text-slate-500 text-sm font-mono">{client.overlay_ip}</p>
                                    </div>
                                </div>
                                <div className="relative">
                                    <button
                                        onClick={() => setOpenMenu(openMenu === client.id ? null : client.id)}
                                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                                    >
                                        <MoreVertical className="w-4 h-4" />
                                    </button>
                                    {openMenu === client.id && (
                                        <div className="absolute right-0 mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-10 min-w-[140px]">
                                            <button
                                                onClick={() => {
                                                    handleDownloadConfig(client)
                                                    setOpenMenu(null)
                                                }}
                                                className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 flex items-center gap-2"
                                            >
                                                <Download className="w-3.5 h-3.5" />
                                                Download Config
                                            </button>
                                            {client.status !== 'revoked' && (
                                                <button
                                                    onClick={() => {
                                                        revokeMutation.mutate(client.id)
                                                        setOpenMenu(null)
                                                    }}
                                                    className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-slate-800 flex items-center gap-2"
                                                >
                                                    <XCircle className="w-3.5 h-3.5" />
                                                    Revoke Access
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-4 flex items-center justify-between">
                                <StatusBadge status={client.status} />
                                <span className="text-xs text-slate-500 capitalize">{client.tunnel_mode} tunnel</span>
                            </div>

                            {!client.config_downloaded && client.status === 'active' && (
                                <button
                                    onClick={() => handleDownloadConfig(client)}
                                    className="mt-3 w-full btn btn-secondary btn-sm gap-2 justify-center"
                                >
                                    <QrCode className="w-3.5 h-3.5" />
                                    Get Configuration
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Summary */}
            <div className="flex items-center gap-4 text-sm text-slate-500">
                <span>Total: {clients.length} devices</span>
                <span>•</span>
                <span>Showing: {filteredClients.length}</span>
            </div>

            {/* Modals */}
            <CreateClientModal
                isOpen={showCreateModal}
                onClose={() => setShowCreateModal(false)}
                onCreate={handleCreate}
            />
            <ConfigModal
                isOpen={configModal.open}
                onClose={() => setConfigModal({ open: false, config: null, name: '' })}
                config={configModal.config}
                deviceName={configModal.name}
            />
        </div>
    )
}
