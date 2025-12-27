import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import NodesPage from './pages/NodesPage'
import ClientsPage from './pages/ClientsPage'
import UsersPage from './pages/UsersPage'
import PoliciesPage from './pages/PoliciesPage'
import EventsPage from './pages/EventsPage'

function App() {
    return (
        <Routes>
            <Route path="/" element={<Layout />}>
                <Route index element={<DashboardPage />} />
                <Route path="nodes" element={<NodesPage />} />
                <Route path="clients" element={<ClientsPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route path="policies" element={<PoliciesPage />} />
                <Route path="events" element={<EventsPage />} />
            </Route>
        </Routes>
    )
}

export default App
