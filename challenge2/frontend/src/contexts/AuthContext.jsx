import { createContext, useContext, useState, useCallback } from 'react'
import { authApi } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('sc_token'))
  const [org, setOrg] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sc_org') || 'null') } catch { return null }
  })

  const login = useCallback(async (email, password) => {
    const res = await authApi.login(email, password)
    const { access_token, org_name, org_id } = res.data
    localStorage.setItem('sc_token', access_token)
    const orgData = { name: org_name, id: org_id }
    localStorage.setItem('sc_org', JSON.stringify(orgData))
    setToken(access_token)
    setOrg(orgData)
    return orgData
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('sc_token')
    localStorage.removeItem('sc_org')
    setToken(null)
    setOrg(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, org, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
