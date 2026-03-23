import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts'
import { solarApi, adminApi } from '../api'
import { Sun, Thermometer, Zap, AlertTriangle } from 'lucide-react'
import { format, parseISO } from 'date-fns'

export default function SolarView({ site, liveData }) {
  const [readings, setReadings] = useState([])
  const [hours, setHours] = useState(24)
  const [faultActive, setFaultActive] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    solarApi.readings(site.id, hours).then((res) => {
      setReadings(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [site.id, hours])

  // Live update appends the latest reading
  useEffect(() => {
    if (liveData) {
      setReadings((prev) => {
        const newEntry = {
          ts: liveData.ts,
          power_kw: liveData.power_kw,
          expected_kw: prev[prev.length - 1]?.expected_kw || 0,
          anomaly_flag: liveData.anomaly_flag,
          anomaly_severity: liveData.anomaly_severity,
        }
        return [...prev.slice(-287), newEntry] // keep ~24h of 5-min samples
      })
    }
  }, [liveData])

  const chartData = readings.map((r) => ({
    time: format(parseISO(r.ts), 'HH:mm'),
    'Actual (kW)': parseFloat(r.power_kw?.toFixed(2) || 0),
    'Expected (kW)': parseFloat(r.expected_kw?.toFixed(2) || 0),
    anomaly: r.anomaly_flag,
  }))

  const latest = readings[readings.length - 1]
  const anomalyCount = readings.filter((r) => r.anomaly_flag).length

  const toggleFault = async () => {
    if (faultActive) {
      await adminApi.clearFault(site.id)
    } else {
      await adminApi.injectFault(site.id, 60)
    }
    setFaultActive(!faultActive)
  }

  return (
    <div className="space-y-4">
      {/* Site header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">{site.name}</h2>
          <p className="text-gray-400 text-sm">{site.solar_kwp} kWp installed · {site.charger_count} EV chargers</p>
        </div>
        <div className="flex gap-2 items-center">
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 text-sm text-white px-3 py-1.5 rounded-lg outline-none"
          >
            <option value={6}>Last 6h</option>
            <option value={24}>Last 24h</option>
            <option value={72}>Last 3 days</option>
          </select>
          {/* Evaluator fault injection button */}
          <button
            onClick={toggleFault}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              faultActive
                ? 'bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30'
                : 'border-gray-700 text-gray-400 hover:border-red-400 hover:text-red-400'
            }`}
          >
            {faultActive ? '⚠ Fault Active' : 'Inject Fault'}
          </button>
        </div>
      </div>

      {/* Live status cards */}
      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="card">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="w-4 h-4 text-brand-teal" />
              <span className="text-xs text-gray-400">Power Now</span>
            </div>
            <div className="text-2xl font-bold text-brand-teal">{latest.power_kw?.toFixed(2)} kW</div>
          </div>
          <div className="card">
            <div className="flex items-center gap-2 mb-1">
              <Sun className="w-4 h-4 text-brand-gold" />
              <span className="text-xs text-gray-400">Energy Today</span>
            </div>
            <div className="text-2xl font-bold text-brand-gold">{latest.energy_kwh?.toFixed(1)} kWh</div>
          </div>
          <div className="card">
            <div className="flex items-center gap-2 mb-1">
              <Thermometer className="w-4 h-4 text-orange-400" />
              <span className="text-xs text-gray-400">Panel Temp</span>
            </div>
            <div className="text-2xl font-bold text-orange-400">{latest.temp_c?.toFixed(1)}°C</div>
          </div>
          <div className="card">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className={`w-4 h-4 ${anomalyCount > 0 ? 'text-red-400' : 'text-green-400'}`} />
              <span className="text-xs text-gray-400">Anomalies</span>
            </div>
            <div className={`text-2xl font-bold ${anomalyCount > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {anomalyCount}
            </div>
          </div>
        </div>
      )}

      {/* Solar generation chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white">Solar Generation vs Expected</h3>
          {liveData?.anomaly_flag && (
            <span className="badge-critical flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> {liveData.anomaly_severity} — Anomaly Detected
            </span>
          )}
        </div>
        {loading ? (
          <div className="h-64 flex items-center justify-center text-gray-500">Loading…</div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} unit=" kW" />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af' }}
                itemStyle={{ color: '#e5e7eb' }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />
              <Line
                type="monotone"
                dataKey="Actual (kW)"
                stroke="#00B5CC"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="Expected (kW)"
                stroke="#F5A623"
                strokeWidth={1.5}
                strokeDasharray="5 5"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Performance ratio table */}
      {latest && (
        <div className="card">
          <h3 className="font-semibold text-white mb-3">Current Reading</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-gray-400">Performance Ratio</div>
              <div className="text-white font-medium">{(latest.performance_ratio * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-gray-400">vs Expected</div>
              <div className={`font-medium ${latest.actual_vs_expected_pct < -15 ? 'text-red-400' : 'text-green-400'}`}>
                {latest.actual_vs_expected_pct?.toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-gray-400">Irradiance</div>
              <div className="text-white font-medium">{latest.irradiance?.toFixed(3)} kWh/m²</div>
            </div>
            <div>
              <div className="text-gray-400">Status</div>
              <span className={latest.anomaly_flag ? 'badge-critical' : 'badge-ok'}>
                {latest.anomaly_severity || 'OK'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
