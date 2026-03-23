import { useState } from 'react'
import { reportsApi } from '../api'
import { FileText, Download, Mail, Loader } from 'lucide-react'

export default function ReportsView({ site, org }) {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [digest, setDigest] = useState(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [digestLoading, setDigestLoading] = useState(false)

  const downloadPDF = async () => {
    setPdfLoading(true)
    try {
      const res = await reportsApi.monthlyPdf(year, month)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `SuperChargeSG_Report_${year}_${String(month).padStart(2, '0')}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error(e)
      alert('Failed to generate PDF. Please try again.')
    } finally {
      setPdfLoading(false)
    }
  }

  const generateDigest = async () => {
    setDigestLoading(true)
    setDigest(null)
    try {
      const res = await reportsApi.weeklyDigest(site.id)
      setDigest(res.data)
    } catch (e) {
      console.error(e)
      alert('Failed to generate digest.')
    } finally {
      setDigestLoading(false)
    }
  }

  const months = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'
  ]

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-white">Reports</h2>

      {/* Monthly PDF */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-brand-teal" />
          <h3 className="font-semibold text-white">Monthly PDF Report</h3>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Branded monthly energy report with site summary, savings chart, anomaly log, and ECIS credits earned.
        </p>
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Year</label>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 text-white text-sm px-3 py-2 rounded-lg outline-none"
            >
              {[2024, 2025, 2026].map((y) => <option key={y}>{y}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Month</label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 text-white text-sm px-3 py-2 rounded-lg outline-none"
            >
              {months.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
            </select>
          </div>
          <button
            onClick={downloadPDF}
            disabled={pdfLoading}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {pdfLoading ? <Loader className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {pdfLoading ? 'Generating…' : 'Download PDF'}
          </button>
        </div>
      </div>

      {/* AI Weekly Digest */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Mail className="w-5 h-5 text-brand-gold" />
          <h3 className="font-semibold text-white">AI Weekly Digest</h3>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Generate a plain-English weekly energy summary for <strong className="text-white">{site.name}</strong>.
          Auto-sent by email every Monday.
        </p>
        <button
          onClick={generateDigest}
          disabled={digestLoading}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          {digestLoading ? <Loader className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
          {digestLoading ? 'Generating…' : 'Generate Digest Preview'}
        </button>

        {digest && (
          <div className="mt-4 bg-gray-800 border border-gray-700 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs text-gray-400 uppercase tracking-wider">AI-Generated Digest</span>
              <span className="text-xs bg-brand-teal/20 text-brand-teal border border-brand-teal/30 px-2 py-0.5 rounded-full">Preview</span>
            </div>
            <div className="text-sm text-gray-200 whitespace-pre-line leading-relaxed">{digest.digest}</div>
            {digest.site_data && (
              <div className="mt-4 pt-4 border-t border-gray-700 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div><span className="text-gray-500">Solar (kWh)</span><div className="text-white font-medium">{digest.site_data.solar_kwh}</div></div>
                <div><span className="text-gray-500">ECIS Credits</span><div className="text-white font-medium">SGD {digest.site_data.ecis_credits}</div></div>
                <div><span className="text-gray-500">EV Sessions</span><div className="text-white font-medium">{digest.site_data.ev_sessions}</div></div>
                <div><span className="text-gray-500">CO₂ Avoided</span><div className="text-white font-medium">{digest.site_data.co2_kg} kg</div></div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
