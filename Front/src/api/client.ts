import operationsJson from './operations.json'
import type { ApiResponse, ErrorBody, Operation } from './types'

export const operations = operationsJson as Record<string, Operation>
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const TOKEN_KEY = 'commerce.session.token'
export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor(public status: number, public error: ErrorBody, public requestId?: string) { super(error.message); this.name = 'ApiError' }
}
export interface RequestOptions {
  params?: Record<string, unknown>; query?: Record<string, unknown>; body?: unknown;
  version?: number; idempotencyKey?: string; signal?: AbortSignal; raw?: boolean;
}

export function buildPath(template: string, params: Record<string, unknown> = {}, query: Record<string, unknown> = {}) {
  const path = template.replace(/\{([^}]+)\}/g, (_, key: string) => {
    const value = params[key]
    if (value === undefined || value === null || value === '') throw new Error(`缺少路径参数：${key}`)
    return encodeURIComponent(String(value))
  })
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  return path + (search.size ? `?${search}` : '')
}

export async function api<T = unknown>(key: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const result = await transport(key, options)
  if (result instanceof Blob) throw new Error('该请求返回文件，请使用下载功能')
  return result as ApiResponse<T>
}

export async function transport(key: string, options: RequestOptions = {}): Promise<ApiResponse<unknown> | Blob> {
  const op = operations[key]
  if (!op) throw new Error(`接口未在契约中定义：${key}`)
  const headers = new Headers({ Accept: options.raw ? '*/*' : 'application/json' })
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (op.idempotent) headers.set('Idempotency-Key', options.idempotencyKey || crypto.randomUUID())
  if (op.concurrency) {
    if (!Number.isInteger(options.version) || Number(options.version) < 1) throw new Error('缺少当前版本，请刷新后重试')
    headers.set('If-Match', `"${options.version}"`)
  }
  let body: BodyInit | undefined
  if (options.body instanceof FormData) body = options.body
  else if (options.body !== undefined) { headers.set('Content-Type', 'application/json'); body = JSON.stringify(options.body) }
  const timeout = new AbortController()
  const timeoutMs = options.body instanceof FormData ? 15 * 60 * 1000 : 45000
  const timer = setTimeout(() => timeout.abort(new Error('请求超时，请检查连接；提交任务请先查询受理结果')), timeoutMs)
  const signal = options.signal ? AbortSignal.any([options.signal, timeout.signal]) : timeout.signal
  let response: Response
  try {
    response = await fetch(API_BASE + buildPath(op.path, options.params, options.query), { method: op.method, headers, body, signal, credentials: 'same-origin', cache: 'no-store' })
  } catch (cause) {
    if (options.signal?.aborted) throw cause
    throw new ApiError(0, { code: 'CONNECTION_FAILED', message: timeout.signal.aborted ? '请求超时，请稍后重试' : '暂时无法连接服务，请检查服务地址或稍后重试', details: [], retryable: true })
  } finally { clearTimeout(timer) }
  if (response.ok && options.raw) return response.blob()
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('json') ? await response.json().catch(() => null) : null
  if (!response.ok) {
    if (response.status === 401 && !op.path.startsWith('/auth/')) window.dispatchEvent(new Event('commerce:unauthorized'))
    const fallback = response.status === 401 ? '登录已失效，请重新登录' : response.status === 403 ? '你没有执行此操作的权限' : response.status === 412 ? '内容已被更新，请刷新后重新提交' : `请求未成功（${response.status}）`
    throw new ApiError(response.status, payload?.error || { code: 'HTTP_ERROR', message: fallback, details: [], retryable: response.status >= 500 }, payload?.request_id || response.headers.get('x-request-id') || undefined)
  }
  if (!payload || !('data' in payload) || !payload.meta?.request_id) throw new ApiError(response.status, { code: 'INVALID_RESPONSE', message: '服务返回的数据格式与接口契约不一致', details: [], retryable: false })
  return payload as ApiResponse<unknown>
}

export async function download(key: string) {
  const blob = await transport(key, { raw: true }) as Blob
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = key.split('/').at(-1) + '.csv'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
