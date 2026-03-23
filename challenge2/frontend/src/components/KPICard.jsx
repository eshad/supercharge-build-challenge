const colorMap = {
  teal: 'text-brand-teal',
  gold: 'text-brand-gold',
  green: 'text-green-400',
  red: 'text-red-400',
}

export default function KPICard({ label, value, color = 'teal' }) {
  return (
    <div className="card flex flex-col justify-between min-h-[80px]">
      <span className={`text-2xl font-bold ${colorMap[color] || 'text-brand-teal'}`}>{value}</span>
      <span className="text-xs text-gray-400 uppercase tracking-wide mt-1">{label}</span>
    </div>
  )
}
