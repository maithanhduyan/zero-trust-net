import { Link, Outlet, useLocation } from 'react-router-dom'
import {
    LayoutDashboard,
    Server,
    Smartphone,
    Users,
    Shield,
    Activity,
    Settings,
    Menu,
    X,
} from 'lucide-react'
import { useState } from 'react'

const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Nodes', href: '/nodes', icon: Server },
    { name: 'Clients', href: '/clients', icon: Smartphone },
    { name: 'Users', href: '/users', icon: Users },
    { name: 'Policies', href: '/policies', icon: Shield },
    { name: 'Events', href: '/events', icon: Activity },
]

export default function Layout() {
    const location = useLocation()
    const [sidebarOpen, setSidebarOpen] = useState(true)

    return (
        <div className="min-h-screen bg-zt-darker">
            {/* Sidebar */}
            <aside
                className={`fixed inset-y-0 left-0 z-50 flex flex-col transition-all duration-300 ${sidebarOpen ? 'w-64' : 'w-16'
                    } bg-zt-dark border-r border-slate-800`}
            >
                {/* Logo */}
                <div className="flex h-16 items-center justify-between px-4 border-b border-slate-800">
                    {sidebarOpen && (
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg flex items-center justify-center">
                                <Shield className="w-5 h-5 text-white" />
                            </div>
                            <span className="font-bold text-white">Zero Trust</span>
                        </div>
                    )}
                    <button
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                    >
                        {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                    </button>
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-3 py-4 space-y-1">
                    {navigation.map((item) => {
                        const isActive = location.pathname === item.href
                        return (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${isActive
                                        ? 'bg-blue-600 text-white'
                                        : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                                    }`}
                                title={!sidebarOpen ? item.name : undefined}
                            >
                                <item.icon className="w-5 h-5 flex-shrink-0" />
                                {sidebarOpen && <span className="font-medium">{item.name}</span>}
                            </Link>
                        )
                    })}
                </nav>

                {/* Settings */}
                <div className="px-3 py-4 border-t border-slate-800">
                    <button
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white w-full`}
                    >
                        <Settings className="w-5 h-5 flex-shrink-0" />
                        {sidebarOpen && <span className="font-medium">Settings</span>}
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <main
                className={`transition-all duration-300 ${sidebarOpen ? 'ml-64' : 'ml-16'
                    }`}
            >
                <Outlet />
            </main>
        </div>
    )
}
