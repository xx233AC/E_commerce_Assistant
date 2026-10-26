import type { Entity } from '../api/types'
export const text = (value: unknown, fallback = '—') => value === null || value === undefined || value === '' ? fallback : String(value)
export const money = (value: unknown) => value === null || value === undefined ? '—' : Number.isFinite(Number(value)) ? `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'
export const count = (value: unknown) => value === null || value === undefined ? '—' : Number.isFinite(Number(value)) ? Number(value).toLocaleString('zh-CN') : '—'
export const percent = (value: unknown) => value === null || value === undefined ? '—' : `${(Number(value) * 100).toFixed(2)}%`
export const dateTime = (value: unknown) => !value || !Number.isFinite(new Date(String(value)).getTime()) ? '—' : new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(String(value)))
export const shortId = (id: unknown) => typeof id === 'string' ? id.slice(0, 8) : '—'
export const refOf = (row: Entity) => ({ id: row.id, version: row.version })
export const today = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date())
export const isEntity = (v: unknown): v is Entity => typeof v === 'object' && v !== null && !Array.isArray(v)
