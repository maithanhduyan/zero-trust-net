import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    Users as UsersIcon,
    Search,
    Plus,
    MoreVertical,
    Trash2,
    UserPlus,
    FolderPlus
} from 'lucide-react'
import { getUsers, getGroups, createUser, deleteUser, createGroup, deleteGroup } from '@/lib/api'

function CreateUserModal({
    isOpen,
    onClose,
    onCreate
}: {
    isOpen: boolean
    onClose: () => void
    onCreate: (data: { username: string; email?: string }) => void
}) {
    const [username, setUsername] = useState('')
    const [email, setEmail] = useState('')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onCreate({ username, email: email || undefined })
        setUsername('')
        setEmail('')
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-md shadow-xl">
                <div className="p-6 border-b border-slate-800">
                    <h2 className="text-lg font-semibold text-white">Create User</h2>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Username</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="e.g., john.doe"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Email (optional)</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="e.g., john@example.com"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div className="flex gap-3 pt-4">
                        <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary flex-1">
                            Create User
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

function CreateGroupModal({
    isOpen,
    onClose,
    onCreate
}: {
    isOpen: boolean
    onClose: () => void
    onCreate: (data: { name: string; description?: string }) => void
}) {
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onCreate({ name, description: description || undefined })
        setName('')
        setDescription('')
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-md shadow-xl">
                <div className="p-6 border-b border-slate-800">
                    <h2 className="text-lg font-semibold text-white">Create Group</h2>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Group Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g., developers"
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">Description (optional)</label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Group description..."
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 h-20 resize-none"
                        />
                    </div>
                    <div className="flex gap-3 pt-4">
                        <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary flex-1">
                            Create Group
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export default function UsersPage() {
    const queryClient = useQueryClient()
    const [activeTab, setActiveTab] = useState<'users' | 'groups'>('users')
    const [search, setSearch] = useState('')
    const [showCreateUserModal, setShowCreateUserModal] = useState(false)
    const [showCreateGroupModal, setShowCreateGroupModal] = useState(false)
    const [openMenu, setOpenMenu] = useState<number | null>(null)

    const { data: users = [], isLoading: usersLoading } = useQuery({
        queryKey: ['users'],
        queryFn: getUsers,
    })

    const { data: groups = [], isLoading: groupsLoading } = useQuery({
        queryKey: ['groups'],
        queryFn: getGroups,
    })

    const createUserMutation = useMutation({
        mutationFn: createUser,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
    })

    const deleteUserMutation = useMutation({
        mutationFn: deleteUser,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
    })

    const createGroupMutation = useMutation({
        mutationFn: createGroup,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['groups'] }),
    })

    const deleteGroupMutation = useMutation({
        mutationFn: deleteGroup,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['groups'] }),
    })

    const filteredUsers = users.filter((user) =>
        user.username.toLowerCase().includes(search.toLowerCase()) ||
        user.email?.toLowerCase().includes(search.toLowerCase())
    )

    const filteredGroups = groups.filter((group) =>
        group.name.toLowerCase().includes(search.toLowerCase())
    )

    const isLoading = activeTab === 'users' ? usersLoading : groupsLoading

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Users & Groups</h1>
                    <p className="text-slate-400 mt-1">Manage user accounts and group memberships</p>
                </div>
                <button
                    onClick={() => activeTab === 'users' ? setShowCreateUserModal(true) : setShowCreateGroupModal(true)}
                    className="btn btn-primary gap-2"
                >
                    <Plus className="w-4 h-4" />
                    {activeTab === 'users' ? 'Add User' : 'Add Group'}
                </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 bg-slate-900 p-1 rounded-lg w-fit">
                <button
                    onClick={() => setActiveTab('users')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'users'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-400 hover:text-white'
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <UserPlus className="w-4 h-4" />
                        Users ({users.length})
                    </span>
                </button>
                <button
                    onClick={() => setActiveTab('groups')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'groups'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-400 hover:text-white'
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <FolderPlus className="w-4 h-4" />
                        Groups ({groups.length})
                    </span>
                </button>
            </div>

            {/* Search */}
            <div className="relative max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                    type="text"
                    placeholder={`Search ${activeTab}...`}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
            </div>

            {/* Content */}
            {activeTab === 'users' ? (
                <div className="card overflow-hidden">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-slate-800">
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    User
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Groups
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                    Created
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
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-24" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-20" /></td>
                                        <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-8 ml-auto" /></td>
                                    </tr>
                                ))
                            ) : filteredUsers.length === 0 ? (
                                <tr>
                                    <td colSpan={4} className="px-6 py-12 text-center text-slate-400">
                                        <UsersIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                        <p>No users found</p>
                                    </td>
                                </tr>
                            ) : (
                                filteredUsers.map((user) => (
                                    <tr key={user.id} className="hover:bg-slate-900/50 transition-colors">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 bg-purple-500/10 rounded-full flex items-center justify-center text-purple-400 font-medium">
                                                    {user.username.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <p className="text-white font-medium">{user.username}</p>
                                                    {user.email && <p className="text-slate-500 text-sm">{user.email}</p>}
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-wrap gap-1">
                                                {user.groups && user.groups.length > 0 ? (
                                                    user.groups.map((group, i) => (
                                                        <span key={i} className="px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-400">
                                                            {group}
                                                        </span>
                                                    ))
                                                ) : (
                                                    <span className="text-slate-500 text-sm">No groups</span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-slate-400 text-sm">
                                            {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="relative">
                                                <button
                                                    onClick={() => setOpenMenu(openMenu === user.id ? null : user.id)}
                                                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                                                >
                                                    <MoreVertical className="w-4 h-4" />
                                                </button>
                                                {openMenu === user.id && (
                                                    <div className="absolute right-0 mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-10 min-w-[120px]">
                                                        <button
                                                            onClick={() => {
                                                                deleteUserMutation.mutate(user.id)
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
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {groupsLoading ? (
                        [...Array(6)].map((_, i) => (
                            <div key={i} className="card p-4 animate-pulse">
                                <div className="h-5 bg-slate-800 rounded w-24" />
                                <div className="h-4 bg-slate-800 rounded w-full mt-2" />
                                <div className="h-4 bg-slate-800 rounded w-16 mt-4" />
                            </div>
                        ))
                    ) : filteredGroups.length === 0 ? (
                        <div className="col-span-full card p-12 text-center">
                            <FolderPlus className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                            <p className="text-slate-400">No groups found</p>
                        </div>
                    ) : (
                        filteredGroups.map((group) => (
                            <div key={group.id} className="card p-4 hover:border-slate-700 transition-colors">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                                            <UsersIcon className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <p className="text-white font-medium">{group.name}</p>
                                            {group.description && (
                                                <p className="text-slate-500 text-sm mt-0.5 line-clamp-1">{group.description}</p>
                                            )}
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => {
                                            if (confirm(`Delete group "${group.name}"?`)) {
                                                deleteGroupMutation.mutate(group.id)
                                            }
                                        }}
                                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-red-400"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="mt-4 text-sm text-slate-500">
                                    {group.member_count ?? 0} members
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}

            {/* Modals */}
            <CreateUserModal
                isOpen={showCreateUserModal}
                onClose={() => setShowCreateUserModal(false)}
                onCreate={(data) => createUserMutation.mutate(data)}
            />
            <CreateGroupModal
                isOpen={showCreateGroupModal}
                onClose={() => setShowCreateGroupModal(false)}
                onCreate={(data) => createGroupMutation.mutate(data)}
            />
        </div>
    )
}
