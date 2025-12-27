import { useEffect, useMemo } from 'react'
import Graph from 'graphology'
import { SigmaContainer, useLoadGraph, useSigma } from '@react-sigma/core'
import { Node, ClientDevice } from '@/types'

// Node colors by role
const ROLE_COLORS: Record<string, string> = {
    hub: '#3b82f6',      // Blue
    app: '#22c55e',      // Green
    db: '#f97316',       // Orange
    ops: '#a855f7',      // Purple
    monitor: '#06b6d4',  // Cyan
    gateway: '#eab308',  // Yellow
    client: '#ec4899',   // Pink
    mobile: '#f472b6',   // Pink light
    laptop: '#c084fc',   // Purple light
    desktop: '#fb7185',  // Rose
    user: '#94a3b8',     // Slate
    group: '#2dd4bf',    // Teal
}

// Node sizes by type
const NODE_SIZES: Record<string, number> = {
    hub: 25,
    app: 15,
    db: 15,
    ops: 12,
    monitor: 12,
    gateway: 15,
    client: 10,
    mobile: 8,
    laptop: 10,
    desktop: 10,
}

// Status colors for edges
const STATUS_COLORS: Record<string, string> = {
    active: '#22c55e',
    pending: '#eab308',
    suspended: '#f97316',
    revoked: '#ef4444',
}

interface NetworkGraphProps {
    nodes: Node[]
    clients?: ClientDevice[]
    onNodeClick?: (nodeId: string, data: Node | ClientDevice) => void
    showClients?: boolean
}

// Graph loader component
function GraphLoader({
    nodes,
    clients,
    onNodeClick,
    showClients
}: NetworkGraphProps) {
    const loadGraph = useLoadGraph()
    const sigma = useSigma()

    useEffect(() => {
        const graph = new Graph()

        // Find hub node (center of graph)
        const hubNode = nodes.find((n) => n.role === 'hub')

        // Add hub node at center
        if (hubNode) {
            graph.addNode(`node-${hubNode.id}`, {
                x: 0,
                y: 0,
                size: NODE_SIZES.hub,
                color: ROLE_COLORS.hub,
                label: hubNode.hostname,
                type: 'circle',
                nodeData: hubNode,
            })
        }

        // Add other nodes in a circle around hub
        const otherNodes = nodes.filter((n) => n.role !== 'hub')
        const nodeCount = otherNodes.length
        const radius = 200

        otherNodes.forEach((node, index) => {
            const angle = (2 * Math.PI * index) / nodeCount
            const x = radius * Math.cos(angle)
            const y = radius * Math.sin(angle)

            graph.addNode(`node-${node.id}`, {
                x,
                y,
                size: NODE_SIZES[node.role] || 12,
                color: node.status === 'active'
                    ? ROLE_COLORS[node.role] || '#64748b'
                    : '#475569',
                label: node.hostname,
                type: 'circle',
                nodeData: node,
            })

            // Add edge to hub
            if (hubNode) {
                graph.addEdge(`node-${node.id}`, `node-${hubNode.id}`, {
                    size: node.status === 'active' ? 2 : 1,
                    color: STATUS_COLORS[node.status] || '#475569',
                    type: 'line',
                })
            }
        })

        // Add client devices if enabled
        if (showClients && clients && hubNode) {
            const clientRadius = 350
            clients.forEach((client, index) => {
                const angle = (2 * Math.PI * index) / clients.length + Math.PI / clients.length
                const x = clientRadius * Math.cos(angle)
                const y = clientRadius * Math.sin(angle)

                graph.addNode(`client-${client.id}`, {
                    x,
                    y,
                    size: NODE_SIZES[client.device_type] || 8,
                    color: client.status === 'active'
                        ? ROLE_COLORS[client.device_type] || ROLE_COLORS.client
                        : '#475569',
                    label: client.device_name,
                    type: 'circle',
                    nodeData: client,
                })

                // Edge to hub
                graph.addEdge(`client-${client.id}`, `node-${hubNode.id}`, {
                    size: 1,
                    color: STATUS_COLORS[client.status] || '#475569',
                    type: 'line',
                })
            })
        }

        loadGraph(graph)

        // Setup click handler
        sigma.on('clickNode', ({ node }) => {
            const nodeData = graph.getNodeAttribute(node, 'nodeData')
            if (onNodeClick && nodeData) {
                onNodeClick(node, nodeData)
            }
        })

        return () => {
            sigma.removeAllListeners('clickNode')
        }
    }, [nodes, clients, showClients, loadGraph, sigma, onNodeClick])

    return null
}

export default function NetworkGraph({
    nodes,
    clients = [],
    onNodeClick,
    showClients = true,
}: NetworkGraphProps) {
    const settings = useMemo(
        () => ({
            allowInvalidContainer: true,
            renderLabels: true,
            labelFont: 'Inter, system-ui, sans-serif',
            labelSize: 12,
            labelWeight: '500',
            labelColor: { color: '#e2e8f0' },
            defaultNodeColor: '#64748b',
            defaultEdgeColor: '#334155',
            nodeReducer: (_node: string, data: Record<string, unknown>) => {
                return { ...data }
            },
            edgeReducer: (_edge: string, data: Record<string, unknown>) => {
                return { ...data }
            },
        }),
        []
    )

    if (nodes.length === 0) {
        return (
            <div className="w-full h-full flex items-center justify-center text-slate-500">
                <div className="text-center">
                    <p className="text-lg font-medium">No nodes connected</p>
                    <p className="text-sm">Nodes will appear here when they register</p>
                </div>
            </div>
        )
    }

    return (
        <div className="w-full h-full relative">
            <SigmaContainer
                className="sigma-container"
                settings={settings}
            >
                <GraphLoader
                    nodes={nodes}
                    clients={clients}
                    onNodeClick={onNodeClick}
                    showClients={showClients}
                />
            </SigmaContainer>

            {/* Legend */}
            <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur-sm rounded-lg p-4 border border-slate-700">
                <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Legend</h4>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
                    {Object.entries(ROLE_COLORS).slice(0, 8).map(([role, color]) => (
                        <div key={role} className="flex items-center gap-2">
                            <div
                                className="w-3 h-3 rounded-full"
                                style={{ backgroundColor: color }}
                            />
                            <span className="text-slate-400 capitalize">{role}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
