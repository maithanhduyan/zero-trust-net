import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Eye, EyeOff, Filter } from 'lucide-react'
import { useSigma } from '@react-sigma/core'
import { useState } from 'react'

interface GraphControlsProps {
    showClients: boolean
    onToggleClients: () => void
    selectedFilter: string
    onFilterChange: (filter: string) => void
}

export default function GraphControls({
    showClients,
    onToggleClients,
    selectedFilter,
    onFilterChange,
}: GraphControlsProps) {
    const sigma = useSigma()
    const [isFilterOpen, setIsFilterOpen] = useState(false)

    const filters = [
        { value: 'all', label: 'All Nodes' },
        { value: 'active', label: 'Active Only' },
        { value: 'pending', label: 'Pending Only' },
        { value: 'hub', label: 'Hubs Only' },
        { value: 'high-risk', label: 'High Risk' },
    ]

    const handleZoomIn = () => {
        const camera = sigma.getCamera()
        camera.animatedZoom({ duration: 200 })
    }

    const handleZoomOut = () => {
        const camera = sigma.getCamera()
        camera.animatedUnzoom({ duration: 200 })
    }

    const handleFitView = () => {
        const camera = sigma.getCamera()
        camera.animatedReset({ duration: 300 })
    }

    const handleResetLayout = () => {
        // Re-apply layout - this would require re-running the layout algorithm
        const camera = sigma.getCamera()
        camera.animatedReset({ duration: 300 })
    }

    return (
        <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
            {/* Zoom Controls */}
            <div className="bg-slate-900/90 backdrop-blur rounded-lg border border-slate-700 overflow-hidden">
                <button
                    onClick={handleZoomIn}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Zoom In"
                >
                    <ZoomIn className="w-4 h-4" />
                </button>
                <div className="border-t border-slate-700" />
                <button
                    onClick={handleZoomOut}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Zoom Out"
                >
                    <ZoomOut className="w-4 h-4" />
                </button>
                <div className="border-t border-slate-700" />
                <button
                    onClick={handleFitView}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Fit View"
                >
                    <Maximize2 className="w-4 h-4" />
                </button>
                <div className="border-t border-slate-700" />
                <button
                    onClick={handleResetLayout}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Reset Layout"
                >
                    <RotateCcw className="w-4 h-4" />
                </button>
            </div>

            {/* Toggle Clients */}
            <button
                onClick={onToggleClients}
                className={`p-2 rounded-lg border transition-colors ${showClients
                        ? 'bg-pink-500/20 border-pink-500/40 text-pink-400'
                        : 'bg-slate-900/90 border-slate-700 text-slate-400 hover:text-white'
                    }`}
                title={showClients ? 'Hide Clients' : 'Show Clients'}
            >
                {showClients ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>

            {/* Filter Dropdown */}
            <div className="relative">
                <button
                    onClick={() => setIsFilterOpen(!isFilterOpen)}
                    className={`p-2 rounded-lg border transition-colors ${selectedFilter !== 'all'
                            ? 'bg-blue-500/20 border-blue-500/40 text-blue-400'
                            : 'bg-slate-900/90 border-slate-700 text-slate-400 hover:text-white'
                        }`}
                    title="Filter Nodes"
                >
                    <Filter className="w-4 h-4" />
                </button>

                {isFilterOpen && (
                    <div className="absolute right-full top-0 mr-2 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden min-w-[140px]">
                        {filters.map((filter) => (
                            <button
                                key={filter.value}
                                onClick={() => {
                                    onFilterChange(filter.value)
                                    setIsFilterOpen(false)
                                }}
                                className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-800 transition-colors ${selectedFilter === filter.value
                                        ? 'text-blue-400 bg-blue-500/10'
                                        : 'text-slate-300'
                                    }`}
                            >
                                {filter.label}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}

// Standalone version for use outside SigmaContainer
export function GraphControlsStandalone({
    showClients,
    onToggleClients,
    selectedFilter,
    onFilterChange,
    onZoomIn,
    onZoomOut,
    onFitView,
    onResetLayout,
}: {
    showClients: boolean
    onToggleClients: () => void
    selectedFilter: string
    onFilterChange: (filter: string) => void
    onZoomIn?: () => void
    onZoomOut?: () => void
    onFitView?: () => void
    onResetLayout?: () => void
}) {
    const [isFilterOpen, setIsFilterOpen] = useState(false)

    const filters = [
        { value: 'all', label: 'All Nodes' },
        { value: 'active', label: 'Active Only' },
        { value: 'pending', label: 'Pending Only' },
        { value: 'hub', label: 'Hubs Only' },
        { value: 'high-risk', label: 'High Risk' },
    ]

    return (
        <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
            {/* Zoom Controls */}
            <div className="bg-slate-900/90 backdrop-blur rounded-lg border border-slate-700 overflow-hidden">
                <button
                    onClick={onZoomIn}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Zoom In"
                >
                    <ZoomIn className="w-4 h-4" />
                </button>
                <div className="border-t border-slate-700" />
                <button
                    onClick={onZoomOut}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Zoom Out"
                >
                    <ZoomOut className="w-4 h-4" />
                </button>
                <div className="border-t border-slate-700" />
                <button
                    onClick={onFitView}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Fit View"
                >
                    <Maximize2 className="w-4 h-4" />
                </button>
                <div className="border-t border-slate-700" />
                <button
                    onClick={onResetLayout}
                    className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors block w-full"
                    title="Reset Layout"
                >
                    <RotateCcw className="w-4 h-4" />
                </button>
            </div>

            {/* Toggle Clients */}
            <button
                onClick={onToggleClients}
                className={`p-2 rounded-lg border transition-colors ${showClients
                        ? 'bg-pink-500/20 border-pink-500/40 text-pink-400'
                        : 'bg-slate-900/90 border-slate-700 text-slate-400 hover:text-white'
                    }`}
                title={showClients ? 'Hide Clients' : 'Show Clients'}
            >
                {showClients ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>

            {/* Filter Dropdown */}
            <div className="relative">
                <button
                    onClick={() => setIsFilterOpen(!isFilterOpen)}
                    className={`p-2 rounded-lg border transition-colors ${selectedFilter !== 'all'
                            ? 'bg-blue-500/20 border-blue-500/40 text-blue-400'
                            : 'bg-slate-900/90 border-slate-700 text-slate-400 hover:text-white'
                        }`}
                    title="Filter Nodes"
                >
                    <Filter className="w-4 h-4" />
                </button>

                {isFilterOpen && (
                    <div className="absolute right-full top-0 mr-2 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden min-w-[140px]">
                        {filters.map((filter) => (
                            <button
                                key={filter.value}
                                onClick={() => {
                                    onFilterChange(filter.value)
                                    setIsFilterOpen(false)
                                }}
                                className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-800 transition-colors ${selectedFilter === filter.value
                                        ? 'text-blue-400 bg-blue-500/10'
                                        : 'text-slate-300'
                                    }`}
                            >
                                {filter.label}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
