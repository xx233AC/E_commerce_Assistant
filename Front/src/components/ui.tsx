import { useEffect, useId, useRef } from 'react'
import type { ReactNode, ButtonHTMLAttributes } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { AlertCircle, ArrowRight, ChevronLeft, ChevronRight, CircleDashed, Copy, LoaderCircle, RefreshCw, X } from 'lucide-react'
import { ApiError } from '../api/client'
import type { ApiMeta, Entity } from '../api/types'
import { useNotice, useSession } from '../app/providers'
import { label, stateLabel } from '../lib/labels'
import { dateTime, isEntity, money, percent, text } from '../lib/format'

export function Button({ children, variant = 'secondary', className = '', loading, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; loading?: boolean }) {
  return <button type="button" {...props} disabled={props.disabled || loading} className={`button button-${variant} ${className}`}>{loading && <LoaderCircle size={15} className="spin" />}{children}</button>
}
export function PageHeader({ title, description, actions, eyebrow }: { title: string; description?: string; actions?: ReactNode; eyebrow?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <div className="breadcrumb">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div><div className="header-actions">{actions}</div></header>
}
export function Panel({ title, description, actions, children, className = '' }: { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{title && <div className="panel-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{actions}</div>}<div className="panel-body">{children}</div></section>
}
export function Empty({ title = '暂无记录', description, action }: { title?: string; description?: string; action?: ReactNode }) {
  return <div className="empty"><CircleDashed size={24} strokeWidth={1.4} /><h3>{title}</h3>{description && <p>{description}</p>}{action}</div>
}
export function Loading({ rows = 3 }: { rows?: number }) { return <div className="loading" role="status" aria-label="正在加载"><span className="sr-only">正在加载</span>{Array.from({ length: rows }, (_, i) => <div className="skeleton-row" key={i}><i /><i /><i /></div>)}</div> }
export function ErrorMessage({ error, retry }: { error: unknown; retry?: () => void }) {
  const err = error instanceof Error ? error : new Error('操作未完成')
  return <div className="error-box" role="alert"><AlertCircle size={18} /><div><strong>{err.message}</strong>{error instanceof ApiError && <>{error.error.details?.length > 0 && <ul>{error.error.details.map((d, i) => <li key={i}>{d.row_number ? `第 ${d.row_number} 行 · ` : ''}{d.field ? `${label(d.field)}：` : ''}{d.message}</li>)}</ul>}{error.requestId && <small>请求编号：{error.requestId}</small>}{error.status === 412 && <p>请关闭编辑窗口并刷新，查看最新内容后重新提交。</p>}</>}</div>{retry && <Button variant="ghost" onClick={retry}><RefreshCw size={14} />重试</Button>}</div>
}
export function SessionGate({ children }: { children: ReactNode }) {
  const { user, loading, error, retry } = useSession()
  const location = useLocation()
  if (loading) return <Loading rows={5} />
  if (error) return <ErrorMessage error={error} retry={retry} />
  if (!user) return <Empty title="登录后开始运营" description="查看店铺商品、处理素材审核，并跟进本轮运营进展。" action={<Link className="button button-primary" to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}>登录工作台<ArrowRight size={15} /></Link>} />
  return <>{children}</>
}
export function AdminGate({ children }: { children: ReactNode }) { const { user } = useSession(); return <SessionGate>{user?.role === 'admin' ? children : <Empty title="此页面需要管理员权限" description="请联系店铺管理员处理用户和系统设置。" />}</SessionGate> }
export function Badge({ value }: { value: unknown }) {
  const s = String(value ?? '')
  const tone = ['approved','succeeded','confirmed','active','completed','finished'].includes(s) ? 'positive' : ['failed','rejected','timeout'].includes(s) ? 'negative' : ['running','pending','preview_ready','validating','committing'].includes(s) ? 'warning' : 'neutral'
  return <span className={`badge badge-${tone}`}><span className="status-dot" />{stateLabel(value)}</span>
}
export function CopyButton({ value, name = '复制' }: { value: unknown; name?: string }) {
  const notice = useNotice()
  return <Button variant="ghost" className="icon-button" aria-label={name} title={name} onClick={() => { void navigator.clipboard.writeText(String(value)).then(() => notice('已复制')).catch(() => notice('复制失败，请手动选择文字', 'error')) }}><Copy size={13} /></Button>
}
export function Value({ value, field = '' }: { value: unknown; field?: string }) {
  if (value === undefined || value === null || value === '') return <span className="muted">—</span>
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>
  if (field.endsWith('_status') || ['status','role','execution_mode','granularity','plan_type','job_kind','asset_type','stage','source_type','priority','certainty'].includes(field)) return <Badge value={value} />
  if (['price','cost','budget_amount','budget_cap','daily_cap','amount','total_amount','spend','revenue','cpa'].includes(field)) return <span className="num">{money(value)}</span>
  if (['ctr','conversion_rate'].includes(field)) return <span className="num">{percent(value)}</span>
  if (field.endsWith('_at')) return <span className="num">{dateTime(value)}</span>
  if (Array.isArray(value)) return value.length ? <div className="value-array">{value.map((v, i) => <div key={i}>{isEntity(v) ? <RecordView data={v} compact /> : <Value value={v} />}</div>)}</div> : <span className="muted">无</span>
  if (isEntity(value)) {
    if (Object.keys(value).every(k => ['id','version'].includes(k))) return <span className="id-ref">{text(value.id)} <small>v{String(value.version)}</small></span>
    return <RecordView data={value} compact />
  }
  if (typeof value === 'string' && /^https?:\/\//.test(value)) return <a className="text-link break" href={value} target="_blank" rel="noopener noreferrer">{value}</a>
  if (field === 'id' || field.endsWith('_id')) return <span className="id-ref" title={String(value)}>{String(value).slice(0,8)}<CopyButton value={value} /></span>
  return <span className="preserve">{stateLabel(value)}</span>
}
export function RecordView({ data, fields, compact = false }: { data: Entity; fields?: string[]; compact?: boolean }) {
  const keys = fields || Object.keys(data).filter(k => !['provenance','id','product_id','round_id','store_id','meta'].includes(k))
  return <dl className={`record-view ${compact ? 'compact' : ''}`}>{keys.filter(k => k in data).map(k => <div className="record-field" key={k}><dt>{label(k)}</dt><dd><Value value={data[k]} field={k} /></dd></div>)}</dl>
}
export interface Column { key: string; label?: string; numeric?: boolean; render?: (row: Entity) => ReactNode }
export function DataTable({ rows, columns, actions, onOpen, empty }: { rows: Entity[]; columns: Column[]; actions?: (row: Entity) => ReactNode; onOpen?: (row: Entity) => void; empty?: ReactNode }) {
  if (!rows.length) return empty || <Empty />
  return <div className="table-scroll"><table><thead><tr>{columns.map(c => <th key={c.key} className={c.numeric ? 'numeric' : ''}>{c.label || label(c.key)}</th>)}{actions && <th className="action-cell">操作</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.id || index}>{columns.map((c,i) => <td data-label={c.label || label(c.key)} className={c.numeric ? 'numeric' : ''} key={c.key}>{i === 0 && onOpen ? <button className="row-link" onClick={() => onOpen(row)}>{c.render ? c.render(row) : <Value value={row[c.key]} field={c.key} />}</button> : c.render ? c.render(row) : <Value value={row[c.key]} field={c.key} />}</td>)}{actions && <td className="action-cell"><div className="row-actions">{actions(row)}</div></td>}</tr>)}</tbody></table></div>
}
export function Pagination({ meta, page, onChange }: { meta?: ApiMeta; page: number; onChange: (page: number) => void }) {
  if (!meta) return null
  const size = meta.page_size || 20, total = meta.total || 0
  return <div className="pagination"><span>{total ? `${(page-1)*size+1}–${Math.min(page*size,total)}` : '0'} / 共 {total} 条</span><div><Button aria-label="上一页" disabled={page <= 1} onClick={() => onChange(page-1)}><ChevronLeft size={15} /></Button><span className="num">{page} / {Math.max(1,meta.total_pages || 0)}</span><Button aria-label="下一页" disabled={page >= (meta.total_pages || 0)} onClick={() => onChange(page+1)}><ChevronRight size={15} /></Button></div></div>
}
export function Dialog({ title, children, onClose, wide = false, busy = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean; busy?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null), titleId = useId()
  useEffect(() => { ref.current?.showModal(); return () => ref.current?.close() }, [])
  return <dialog ref={ref} className={`dialog ${wide ? 'dialog-wide' : ''}`} aria-labelledby={titleId} onCancel={e => { e.preventDefault(); if (!busy) onClose() }}><div className="dialog-heading"><h2 id={titleId}>{title}</h2><Button disabled={busy} variant="ghost" className="icon-button" aria-label="关闭窗口" onClick={onClose}><X size={18} /></Button></div>{children}</dialog>
}
