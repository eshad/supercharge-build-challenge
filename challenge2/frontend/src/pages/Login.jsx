import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Zap } from 'lucide-react'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  const fillDemo = (client) => {
    if (client === 'A') {
      setEmail('admin@greenfield-condo.sg')
      setPassword('SuperCharge@ClientA')
    } else {
      setEmail('energy@sentosa-industrial.sg')
      setPassword('SuperCharge@ClientB')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <Zap className="w-10 h-10 text-brand-teal" />
            <span className="text-3xl font-bold text-white">SuperCharge SG</span>
          </div>
          <p className="text-gray-400">Smart Energy Dashboard</p>
        </div>

        {/* Card */}
        <div className="card">
          <h2 className="text-xl font-semibold text-white mb-6">Sign in to your account</h2>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-gray-800 border border-gray-700 focus:border-brand-teal rounded-lg px-3 py-2.5 text-white outline-none transition-colors"
                placeholder="your@email.com"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-gray-800 border border-gray-700 focus:border-brand-teal rounded-lg px-3 py-2.5 text-white outline-none transition-colors"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 text-center rounded-lg disabled:opacity-50"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          {/* Demo credentials */}
          <div className="mt-6 pt-6 border-t border-gray-800">
            <p className="text-xs text-gray-500 mb-3 text-center">Demo accounts for evaluation</p>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => fillDemo('A')} className="btn-ghost text-sm py-2">
                Client A (Greenfield)
              </button>
              <button onClick={() => fillDemo('B')} className="btn-ghost text-sm py-2">
                Client B (Sentosa)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
