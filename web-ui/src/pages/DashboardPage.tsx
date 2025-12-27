import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, AlertCircle } from 'lucide-react'
import { NetworkGraph, NodeDetailsPanel, MetricsCards, DetailedMetrics, RoleDistribution } from '@/components'
import { getNodes, getClientDevices, getUsers, approveNode, suspendNode, revokeNode } from '@/lib/api'
import type { Node, ClientDevice } from '@/types'

export default function DashboardPage() {
    const queryClient = useQueryClient()
    const [selectedNode, setSelectedNode] = useState<Node | ClientDevice | null>(null)
    const [selectedNodeType, setSelectedNodeType] = useState<'node' | 'client'>('node')
    const [showClients, setShowClients] = useState(true)

    // Fetch data
    const { data: nodes = [], isLoading: nodesLoading, error: nodesError, refetch: refetchNodes } = useQuery({
        queryKey: ['nodes'],
        queryFn: getNodes,
        refetchInterval: 30000, // Refresh every 30s
    })

    const { data: clients = [], isLoading: clientsLoading, refetch: refetchClients } = useQuery({
        queryKey: ['clients'],
        queryFn: getClientDevices,
        refetchInterval: 30000,
    })

    const { data: users = [] } = useQuery({
        queryKey: ['users'],
        queryFn: getUsers,
    })

    // Mutations for node actions
    const approveMutation = useMutation({
        mutationFn: approveNode,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nodes'] })
            setSelectedNode(null)
        },
    })

    const suspendMutation = useMutation({
        mutationFn: suspendNode,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nodes'] })
            setSelectedNode(null)
        },
    })

    const revokeMutation = useMutation({
        mutationFn: revokeNode,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nodes'] })
            setSelectedNode(null)
        },
    })

    // Handle node click
    const handleNodeClick = useCallback((nodeId: string, data: Node | ClientDevice) => {
        if (nodeId.startsWith('node-')) {
            setSelectedNode(data)
            setSelectedNodeType('node')
        } else {
            setSelectedNode(data)
            setSelectedNodeType('client')
        }
    }, [])

    // Handle node actions
    const handleAction = useCallback((action: string, id: number) => {
        switch (action) {
            case 'approve':
                approveMutation.mutate(id)
                break
            case 'suspend':
                suspendMutation.mutate(id)
                break
            case 'revoke':
                revokeMutation.mutate(id)
                break
        }
    }, [approveMutation, suspendMutation, revokeMutation])

    // Refresh all data
    const handleRefresh = () => {
        refetchNodes()
        refetchClients()
    }

    const isLoading = nodesLoading || clientsLoading

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                    <p className="text-slate-400 mt-1">Zero Trust Network Overview</p>
                </div>
                <button
                    onClick={handleRefresh}
                    className="btn btn-secondary gap-2"
                    disabled={isLoading}
                >
                    <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Error State */}
            {nodesError && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <div>
                        <p className="text-red-400 font-medium">Failed to load nodes</p>
                        <p className="text-red-400/70 text-sm">
                            {nodesError instanceof Error ? nodesError.message : 'Unknown error'}
                        </p>
                    </div>
                </div>
            )}

            {/* Metrics Cards */}
            <MetricsCards
                nodes={nodes}
                clients={clients}
                users={users}
                isLoading={isLoading}
            />

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
                {/* Network Graph */}
                <div className="xl:col-span-3">
                    <div className="card overflow-hidden">
                        <div className="p-4 border-b border-slate-800">
                            <div className="flex items-center justify-between">
                                <h2 className="text-lg font-semibold text-white">Network Topology</h2>
                                <button
                                    onClick={() => setShowClients(!showClients)}
                                    className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${showClients
                                        ? 'bg-pink-500/20 text-pink-400'
                                        : 'bg-slate-800 text-slate-400'
                                        }`}
                                >
                                    {showClients ? 'Hide Clients' : 'Show Clients'}
                                </button>
                            </div>
                        </div>
                        <div className="h-[500px]">
                            <NetworkGraph
                                nodes={nodes}
                                clients={showClients ? clients : []}
                                onNodeClick={handleNodeClick}
                                showClients={showClients}
                            />
                        </div>
                    </div>
                </div>

                {/* Sidebar Stats */}
                <div className="space-y-6">
                    <DetailedMetrics nodes={nodes} clients={clients} />
                    <RoleDistribution nodes={nodes} />
                </div>
            </div>

            {/* Node Details Panel */}
            <NodeDetailsPanel
                node={selectedNode}
                nodeType={selectedNodeType}
                onClose={() => setSelectedNode(null)}
                onAction={handleAction}
            />
        </div>
    )
}
