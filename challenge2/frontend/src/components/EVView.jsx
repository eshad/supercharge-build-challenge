import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { evApi } from '../api'
import { Zap, Clock, DollarSign } from 'lucide-react'
import { format, parseISO } from 'date-fns'

const STATUS_COLORS = {
  Charging: 'text-green-400 bg-green-400/10 border-green-400/30',
  Available: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  Faulted: 'text-red-400 bg-red-400/10 border-red-400/30',
  Finishing: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  SuspendedEV: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
}

export default function EVView({ site }) {
  const [sessions, setSessions] = useState([])
  const [hours, setHours] = useState(24)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    evApi.sessions(site.id, hours).then((res) => {
      setSessions(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))

    const interval = setInterval(() => {
      evApi.sessions(site.id, hours).then((res) => setSessions(res.data))
    }, 30000)
    return () => clearInterval(interval)
  }, [site.id, hours])

  const completed = sessions.filter((s) => s.end_ts)
  const active = sessions.filter((s) => !s.end_ts)
  const totalKwh = completed.reduce((sum, s) => sum + (s.energy_kwh || 0), 0)
  const totalRevenue = completed.reduce((sum, s) => sum + (s.revenue_sgd || 0), 0)

  // Chart: sessions per charger
  const byCharger = {}
  sessions.forEach((s) => {
    byCharger[s.charger_id] = (byCharger[s.charger_id] || 0) + 1
  })
  const chartData = Object.entries(byCharger).map(([id, count]) => ({
    charger: id.slice(-6), count
  }))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">EV Charging — {site.name}</h2>
        <select
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          className="bg-gray-800 border border-gray-700 text-sm text-white px-3 py-1.5 rounded-lg outline-none"
        >
          <option value={6}>Last 6h</option>
          <option value={24}>Last 24h</option>
          <option value={72}>Last 3 days</option>
        </select>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card">
          <div className="flex items-center gap-2 mb-1"><Zap className="w-4 h-4 text-green-400" /><span className="text-xs text-gray-400">Active</span></div>
          <div className="text-2xl font-bold text-green-400">{active.length}</div>
        </div>
        <div className="card">
          <div className="flex items-center gap-2 mb-1"><Clock className="w-4 h-4 text-brand-teal" /><span className="text-xs text-gray-400">Sessions</span></div>
          <div className="text-2xl font-bold text-brand-teal">{completed.length}</div>
        </div>
        <div className="card">
          <div className="flex items-center gap-2 mb-1"><Zap className="w-4 h-4 text-brand-gold" /><span className="text-xs text-gray-400">Energy Delivered</span></div>
          <div className="text-2xl font-bold text-brand-gold">{totalKwh.toFixed(1)} kWh</div>
        </div>
        <div className="card">
          <div className="flex items-center gap-2 mb-1"><DollarSign className="w-4 h-4 text-emerald-400" /><span className="text-xs text-gray-400">Revenue</span></div>
          <div className="text-2xl font-bold text-emerald-400">SGD {totalRevenue.toFixed(2)}</div>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-white mb-4">Sessions by Charger</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="charger" stroke="#6b7280" tick={{ fontSize: 11 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
              <Bar dataKey="count" fill="#00B5CC" radius={[4, 4, 0, 0]} name="Sessions" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Sessions table */}
      <div className="card">
        <h3 className="font-semibold text-white mb-4">Session Log</h3>
        {loading ? (
          <div className="text-center text-gray-500 py-8">Loading…</div>
        ) : sessions.length === 0 ? (
          <div className="text-center text-gray-500 py-8">No sessions in this period.</div>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 text-xs border-b border-gray-800">
                  <th className="pb-2 text-left">Charger</th>
                  <th className="pb-2 text-left">Start</th>
                  <th className="pb-2 text-left">Status</th>
                  <th className="pb-2 text-right">kWh</th>
                  <th className="pb-2 text-right">SGD</th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 50).map((s) => (
                  <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 text-white font-mono text-xs">{s.charger_id}</td>
                    <td className="py-2 text-gray-400">
                      {format(parseISO(s.start_ts), 'dd/MM HH:mm')}
                    </td>
                    <td className="py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[s.status] || 'text-gray-400 border-gray-700'}`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="py-2 text-right text-brand-teal">{s.energy_kwh?.toFixed(2)}</td>
                    <td className="py-2 text-right text-emerald-400">{s.revenue_sgd?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
