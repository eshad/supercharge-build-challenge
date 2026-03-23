import { useState, useEffect } from 'react'
import { ecisApi } from '../api'
import { Battery, TrendingUp, Leaf } from 'lucide-react'

export default function ECISTracker({ site }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const now = new Date()

  useEffect(() => {
    ecisApi.calculate(site.id, now.getFullYear(), now.getMonth() + 1)
      .then((res) => { setData(res.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [site.id])

  if (loading) return <div className="card h-48 flex items-center justify-center text-gray-500">Calculating…</div>

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold text-white">ECIS Export Credit Tracker</h2>
        <p className="text-gray-400 text-sm">Enhanced Central Intermediary Scheme — Singapore solar export credits</p>
      </div>

      {data && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="card">
              <div className="flex items-center gap-2 mb-2"><Battery className="w-5 h-5 text-brand-teal" /></div>
              <div className="text-3xl font-bold text-brand-teal">{data.solar_kwh_generated.toFixed(1)} kWh</div>
              <div className="text-xs text-gray-400 mt-1">Solar Generated This Month</div>
            </div>
            <div className="card">
              <div className="flex items-center gap-2 mb-2"><TrendingUp className="w-5 h-5 text-brand-gold" /></div>
              <div className="text-3xl font-bold text-brand-gold">{data.estimated_exported_kwh.toFixed(1)} kWh</div>
              <div className="text-xs text-gray-400 mt-1">Estimated Exported (30%)</div>
            </div>
            <div className="card">
              <div className="flex items-center gap-2 mb-2"><Leaf className="w-5 h-5 text-green-400" /></div>
              <div className="text-3xl font-bold text-green-400">SGD {data.ecis_credits_sgd.toFixed(2)}</div>
              <div className="text-xs text-gray-400 mt-1">ECIS Credits Earned</div>
            </div>
          </div>

          {/* Formula breakdown */}
          <div className="card">
            <h3 className="font-semibold text-white mb-4">Credit Calculation</h3>
            <div className="space-y-3">
              <div className="flex justify-between py-2 border-b border-gray-800">
                <span className="text-gray-400">Site</span>
                <span className="text-white">{data.site_name}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-800">
                <span className="text-gray-400">Period</span>
                <span className="text-white">{data.period}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-800">
                <span className="text-gray-400">Solar Generated</span>
                <span className="text-white">{data.solar_kwh_generated.toFixed(2)} kWh</span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-800">
                <span className="text-gray-400">Estimated Export (30%)</span>
                <span className="text-white">{data.estimated_exported_kwh.toFixed(2)} kWh</span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-800">
                <span className="text-gray-400">ECIS Rate</span>
                <span className="text-white">SGD {data.ecis_rate_sgd_kwh}/kWh</span>
              </div>
              <div className="flex justify-between py-2 font-bold">
                <span className="text-brand-teal">ECIS Credits</span>
                <span className="text-brand-teal">SGD {data.ecis_credits_sgd.toFixed(2)}</span>
              </div>
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 text-xs text-blue-300">
                <strong>Formula:</strong> {data.formula} <br />
                <span className="text-gray-400 mt-1 block">{data.note}</span>
              </div>
            </div>
          </div>

          {/* Annual projection */}
          <div className="card">
            <h3 className="font-semibold text-white mb-3">Annual Projection</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-400">Projected Annual ECIS</div>
                <div className="text-2xl font-bold text-green-400">SGD {(data.ecis_credits_sgd * 12).toFixed(0)}</div>
              </div>
              <div>
                <div className="text-gray-400">5kWp System Benchmark</div>
                <div className="text-white font-medium">SGD 1,400–1,700/yr</div>
                <div className="text-xs text-gray-500">Source: SuperCharge SG Knowledge Base</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
