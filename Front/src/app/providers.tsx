import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, operations, tokenStore } from '../api/client'
import type { Entity, User } from '../api/types'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 15000, refetchOnWindowFocus: false }, mutations: { retry: false } } })
type Session = { user: User | null; loading: boolean; error: Error | null; login: (username: string, password: string) => Promise<void>; logout: () => Promise<void>; retry: () => void; can: (key: string) => boolean }
const AuthContext = createContext<Session | null>(null)
const NoticeContext = createContext<(message: string, type?: 'success' | 'error') => void>(() => {})

function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(tokenStore.get)
  const client = useQueryClient()
  const me = useQuery({ queryKey: ['session', token], enabled: !!token, queryFn: ({ signal }) => api<User>('GET /auth/me', { signal }), staleTime: Infinity })
  const clear = useCallback(() => { tokenStore.clear(); setToken(null); client.clear() }, [client])
  useEffect(() => { window.addEventListener('commerce:unauthorized', clear); return () => window.removeEventListener('commerce:unauthorized', clear) }, [clear])
  useEffect(() => { if (me.error instanceof ApiError && me.error.status === 401) clear() }, [me.error, clear])
  const user = token && me.data ? me.data.data : null
  const value = useMemo<Session>(() => ({
    user, loading: !!token && me.isPending, error: token ? me.error : null,
    login: async (username, password) => {
      const result = await api<{ access_token: string; user: User }>('POST /auth/login', { body: { username, password } })
      if (!result.data.access_token || !result.data.user) throw new Error('登录响应缺少用户或令牌')
      client.clear(); tokenStore.set(result.data.access_token)
      client.setQueryData(['session', result.data.access_token], { data: result.data.user, meta: result.meta })
      setToken(result.data.access_token)
    },
    logout: async () => { try { await api('POST /auth/logout') } finally { clear() } },
    retry: () => { void me.refetch() },
    can: (key: string) => !!user && !!operations[key]?.roles.includes(user.role),
  }), [user, token, me.isPending, me.error, client, clear, me.refetch])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

function NoticeProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<{ id: string; message: string; type: string }[]>([])
  const notify = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    const id = crypto.randomUUID()
    setNotices(old => [...old, { id, message, type }])
    setTimeout(() => setNotices(old => old.filter(n => n.id !== id)), 6500)
  }, [])
  return <NoticeContext.Provider value={notify}>{children}<div className="toast-stack" aria-live="polite">{notices.map(n => <div key={n.id} className={`toast toast-${n.type}`}><span>{n.message}</span><button type="button" aria-label="关闭提示" onClick={() => setNotices(old => old.filter(x => x.id !== n.id))}>×</button></div>)}</div></NoticeContext.Provider>
}

export function Providers({ children }: { children: ReactNode }) { return <QueryClientProvider client={queryClient}><AuthProvider><NoticeProvider>{children}</NoticeProvider></AuthProvider></QueryClientProvider> }
export function useSession() { const value = useContext(AuthContext); if (!value) throw new Error('AuthProvider missing'); return value }
export const useNotice = () => useContext(NoticeContext)

export function useResource<T = Entity>(key: string | null, options: import('../api/client').RequestOptions = {}, poll = false) {
  const { user } = useSession()
  return useQuery({
    queryKey: ['api', key, options.params || {}, options.query || {}], enabled: !!user && !!key && !!operations[key]?.roles.includes(user.role),
    queryFn: ({ signal }) => api<T>(key!, { ...options, signal }),
    refetchInterval: poll ? query => {
      const data=query.state.data?.data
      const row=data && typeof data==='object' ? data as Entity : null
      return row && ['succeeded','failed','timeout','cancelled','partially_succeeded','expired'].includes(String(row.job_status || row.status)) ? false : 5000
    } : false,
  })
}

export function useCollection(key: string | null, params: Record<string, unknown> = {}, query: Record<string, unknown> = {}, poll = false) {
  const { user } = useSession()
  return useQuery({
    queryKey: ['api', key, params, query], enabled: !!user && !!key && !!operations[key]?.roles.includes(user.role),
    queryFn: async ({ signal }) => {
      const response = await api<Entity[]>(key!, { params, query, signal })
      if (!Array.isArray(response.data) || typeof response.meta.total !== 'number') throw new Error('列表响应与接口契约不一致')
      return response
    },
    refetchInterval: poll ? 5000 : false,
  })
}
