import { useState, useEffect, useRef, useCallback } from 'react'
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { Zap, Sun, Battery, AlertTriangle, FileText, LogOut, Activity, ChevronDown } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { sitesApi, dashboardApi } from '../api'
import SolarView from '../components/SolarView'
import EVView from '../components/EVView'
import AnomalyPanel from '../components/AnomalyPanel'
import ECISTracker from '../components/ECISTracker'
import ReportsView from '../components/ReportsView'
import KPICard from '../components/KPICard'

const API_URL = import.meta.env.VITE_API_URL || ''
const WS_URL = API_URL.replace(/^http/, 'ws').replace(/^https/, 'wss')

export default function Dashboard() {
  const { org, logout } = useAuth()
  const navigate = useNavigate()
  const [sites, setSites] = useState([])
  const [selectedSite, setSelectedSite] = useState(null)
  const [summary, setSummary] = useState(null)
  const [liveData, setLiveData] = useState({})
  const wsRef = useRef(null)
  const pingRef = useRef(null)

  // Load sites
  useEffect(() => {
    sitesApi.list().then((res) => {
      setSites(res.data)
      if (res.data.length > 0) setSelectedSite(res.data[0])
    })
  }, [])

  // Load summary
  const loadSummary = useCallback(() => {
    dashboardApi.summary().then((res) => setSummary(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    loadSummary()
    const interval = setInterval(loadSummary, 30000)
    return () => clearInterval(interval)
  }, [loadSummary])

  // WebSocket real-time connection
  useEffect(() => {
    if (!org?.id) return
    const orgId = org.id
    const ws = new WebSocket(`${WS_URL}/ws/${orgId}`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send('ping')
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 15000)
    }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'update') {
        const map = {}
        msg.data.forEach((d) => { map[d.site_id] = d })
        setLiveData(map)
      }
    }

    ws.onclose = () => clearInterval(pingRef.current)

    return () => {
      clearInterval(pingRef.current)
      ws.close()
    }
  }, [org?.id])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const nav = [
    { to: '/', icon: Sun, label: 'Solar' },
    { to: '/ev', icon: Zap, label: 'EV Charging' },
    { to: '/anomalies', icon: AlertTriangle, label: 'Anomalies' },
    { to: '/ecis', icon: Battery, label: 'ECIS Credits' },
    { to: '/reports', icon: FileText, label: 'Reports' },
  ]

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top navbar */}
      <header className="bg-brand-dark border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-6 h-6 text-brand-teal" />
            <span className="font-bold text-white">SuperCharge SG</span>
            <span className="text-gray-500 text-sm hidden sm:block">Smart Energy Dashboard</span>
          </div>

          {/* Site selector */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <select
                value={selectedSite?.id || ''}
                onChange={(e) => setSelectedSite(sites.find((s) => s.id === e.target.value))}
                className="appearance-none bg-gray-800 border border-gray-700 text-sm text-white px-3 py-1.5 pr-8 rounded-lg focus:border-brand-teal outline-none"
              >
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2 top-2 pointer-events-none" />
            </div>

            <span className="text-gray-400 text-sm hidden md:block">{org?.name}</span>

            <button onClick={handleLogout} className="text-gray-400 hover:text-white p-1.5 rounded-lg transition-colors" title="Logout">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 max-w-screen-2xl mx-auto w-full">
        {/* Sidebar nav */}
        <aside className="w-52 shrink-0 border-r border-gray-800 py-4 hidden md:block">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm mx-2 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-brand-teal/10 text-brand-teal border border-brand-teal/20'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}

          {/* Live indicator */}
          <div className="mt-4 mx-4 px-3 py-2 bg-gray-900 rounded-lg border border-gray-800">
            <div className="flex items-center gap-2">
              <Activity className="w-3 h-3 text-green-400 animate-pulse" />
              <span className="text-xs text-gray-400">Live — updates every 30s</span>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 p-4 overflow-auto">
          {/* KPI row */}
          {summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
              <KPICard label="Solar Now" value={`${summary.total_solar_kw.toFixed(1)} kW`} color="teal" />
              <KPICard label="Solar Today" value={`${summary.total_solar_kwh_today.toFixed(0)} kWh`} color="teal" />
              <KPICard label="Active Sessions" value={summary.total_ev_sessions_active} color="gold" />
              <KPICard label="EV kWh Today" value={`${summary.total_ev_kwh_today.toFixed(1)} kWh`} color="gold" />
              <KPICard label="ECIS This Month" value={`$${summary.ecis_credits_month.toFixed(2)}`} color="green" />
              <KPICard
                label="Active Alerts"
                value={summary.active_anomalies}
                color={summary.active_anomalies > 0 ? 'red' : 'green'}
              />
            </div>
          )}

          {selectedSite ? (
            <Routes>
              <Route path="/" element={<SolarView site={selectedSite} liveData={liveData[selectedSite?.id]} />} />
              <Route path="/ev" element={<EVView site={selectedSite} />} />
              <Route path="/anomalies" element={<AnomalyPanel sites={sites} />} />
              <Route path="/ecis" element={<ECISTracker site={selectedSite} />} />
              <Route path="/reports" element={<ReportsView site={selectedSite} org={org} />} />
            </Routes>
          ) : (
            <div className="card flex items-center justify-center h-64">
              <p className="text-gray-400">Loading sites…</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
