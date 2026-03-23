import { useState, useEffect } from 'react'
import { anomalyApi } from '../api'
import { AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react'
import { format, parseISO } from 'date-fns'

const SEV_STYLE = {
  CRITICAL: 'badge-critical',
  WARNING: 'badge-warning',
  OK: 'badge-ok',
}

export default function AnomalyPanel({ sites }) {
  const [anomalies, setAnomalies] = useState([])
  const [showResolved, setShowResolved] = useState(false)
  const [loading, setLoading] = useState(true)

  const siteMap = Object.fromEntries(sites.map((s) => [s.id, s.name]))

  const load = () => {
    setLoading(true)
    anomalyApi.list(showResolved).then((res) => {
      setAnomalies(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(load, [showResolved])

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [showResolved])

  const resolve = async (id) => {
    await anomalyApi.resolve(id)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Anomaly Detection</h2>
          <p className="text-gray-400 text-sm">ML-flagged solar yield deviations (&gt;15% below expected)</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="btn-ghost text-sm flex items-center gap-1.5">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button
            onClick={() => setShowResolved(!showResolved)}
            className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${
              showResolved ? 'bg-gray-700 border-gray-600 text-white' : 'border-gray-700 text-gray-400'
            }`}
          >
            {showResolved ? 'Showing Resolved' : 'Show Active'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center h-48 text-gray-500">Loading anomalies…</div>
      ) : anomalies.length === 0 ? (
        <div className="card flex flex-col items-center justify-center h-48 gap-2">
          <CheckCircle className="w-10 h-10 text-green-400" />
          <p className="text-green-400 font-medium">No active anomalies</p>
          <p className="text-gray-500 text-sm">All sites operating within expected parameters.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {anomalies.map((a) => (
            <div key={a.id} className={`card border-l-4 ${a.severity === 'CRITICAL' ? 'border-l-red-500' : 'border-l-yellow-500'}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`w-5 h-5 mt-0.5 ${a.severity === 'CRITICAL' ? 'text-red-400' : 'text-yellow-400'}`} />
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={SEV_STYLE[a.severity] || 'badge-warning'}>{a.severity}</span>
                      <span className="text-white font-medium">{siteMap[a.site_id] || a.site_id}</span>
                    </div>
                    <p className="text-gray-300 text-sm">{a.description}</p>
                    <div className="flex gap-4 mt-2 text-xs text-gray-500">
                      <span>{format(parseISO(a.ts), 'dd MMM HH:mm')}</span>
                      {a.actual_kw != null && <span>Actual: {a.actual_kw.toFixed(2)} kW</span>}
                      {a.expected_kw != null && <span>Expected: {a.expected_kw.toFixed(2)} kW</span>}
                      {a.deviation_pct != null && <span>Deviation: {a.deviation_pct.toFixed(1)}%</span>}
                    </div>
                  </div>
                </div>
                {!showResolved && (
                  <button
                    onClick={() => resolve(a.id)}
                    className="text-xs px-3 py-1.5 border border-gray-700 hover:border-green-400 text-gray-400 hover:text-green-400 rounded-lg transition-colors whitespace-nowrap"
                  >
                    Mark Resolved
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
