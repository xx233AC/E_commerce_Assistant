import { useId, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import { FileUp, Plus, Trash2 } from 'lucide-react'
import schemasJson from '../api/schemas.json'
import { api, operations } from '../api/client'
import type { Entity, Schema } from '../api/types'
import { useSession } from '../app/providers'
import { isEntity, text } from '../lib/format'
import { label, stateLabel } from '../lib/labels'
import { Button, ErrorMessage } from './ui'

export const schemas = schemasJson as Record<string, Schema>
const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: true })
addFormats(ajv)
ajv.addSchema({ $id: 'urn:commerce:schemas', components: { schemas } })
export function resolve(schema: Schema): Schema { return schema.$ref ? schemas[schema.$ref.split('/').at(-1)!] || schema : schema }
export function nonNull(schema: Schema): Schema { const s=resolve(schema); return s.anyOf ? resolve(s.anyOf.find(x => x.type !== 'null') || s) : s }
export function initial(schema: Schema): unknown {
  const raw=resolve(schema)
  if (raw.anyOf?.some(x=>x.type==='null')) return null
  const s=nonNull(schema)
  if (s.default !== undefined) return s.default
  if (s.enum?.length === 1) return s.enum[0]
  if (s.type === 'object') return Object.fromEntries(Object.entries(s.properties || {}).filter(([k,v]) => s.required?.includes(k) || nonNull(v).default !== undefined).map(([k,v]) => [k,initial(v)]))
  if (s.type === 'array') return []
  if (s.type === 'boolean') return false
  if (s.oneOf) return initial(s.oneOf[0])
  return undefined
}
export function editable(schemaName: string, row: Entity): Entity {
  let schema=resolve(schemas[schemaName])
  if (schema.oneOf) schema=resolve(schema.oneOf.find(s => resolve(s).properties?.plan_type?.enum?.includes(String(row.plan_type))) || schema.oneOf[0])
  return Object.fromEntries(Object.keys(schema.properties || {}).filter(k => k in row).map(k => [k,row[k]]))
}
export function validateBody(schemaName: string, value: unknown) {
  const validate=ajv.getSchema('urn:commerce:schemas#/components/schemas/'+schemaName) || ajv.compile({ $ref:'urn:commerce:schemas#/components/schemas/'+schemaName })
  validate(value)
  return (validate.errors || []).filter(e => !['if','oneOf'].includes(e.keyword)).map(e => {
    const path=[...e.instancePath.split('/').filter(Boolean), ...(e.keyword==='required' ? [e.params.missingProperty as string] : [])]
    const field=path.map(k => /^\d+$/.test(k) ? `第${Number(k)+1}项` : label(k)).join(' · ')
    const message=e.keyword==='required' ? '请填写此项' : e.keyword==='format' ? `格式应为${e.params.format==='uuid' ? '有效资源编号' : e.params.format==='date' ? '日期' : e.params.format==='date-time' ? '带时区的时间' : '有效地址'}` : e.keyword==='minItems' ? `至少添加${e.params.limit}项` : e.keyword==='pattern' ? '格式不符合要求，请检查金额小数位或编号' : e.keyword==='minLength' ? `至少${e.params.limit}个字符` : e.keyword==='minimum' ? `不能小于${e.params.limit}` : e.keyword==='maximum' ? `不能大于${e.params.limit}` : e.keyword==='additionalProperties' ? `不接受字段${e.params.additionalProperty}` : e.message || '请检查输入'
    return `${field || '表单'}：${message}`
  })
}

export interface FormContext { productId?: string; roundId?: string; root?: Entity; uploadPurpose?: 'import'|'media'|'reference'|'product_image' }
function lookupFor(field: string, context: FormContext) {
  const p=context.productId
  const product='/products/{product_id}'
  const base: Record<string, { key:string; params?:Entity; query?:Entity }> = {
    store_id:{key:'GET /stores'},product_id:{key:'GET /products'},
    model_config_id:{key:'GET /settings/model-configs'},text_model_config_id:{key:'GET /settings/model-configs'},image_model_config_id:{key:'GET /settings/model-configs'},video_model_config_id:{key:'GET /settings/model-configs'},
  }
  if (p) {
    for (const f of ['round_id','previous_round_id','comparison_round_id']) base[f]={key:`GET ${product}/rounds`,params:{product_id:p}}
    for (const f of ['diagnosis','selected_diagnosis']) base[f]={key:`GET ${product}/diagnoses`,params:{product_id:p},query:context.roundId ? {round_id:context.roundId} : {}}
    for (const f of ['source_review']) base[f]={key:`GET ${product}/review-reports`,params:{product_id:p}}
    for (const f of ['title_plan']) base[f]={key:`GET ${product}/creative-plans`,params:{product_id:p},query:{plan_type:'title',status:'selected', ...(context.roundId ? {round_id:context.roundId} : {})}}
    for (const f of ['related_asset','asset','asset_refs','reference_asset_ids']) base[f]={key:`GET ${product}/assets`,params:{product_id:p},query:{review_status:'approved', ...(context.roundId ? {round_id:context.roundId} : {})}}
    for (const f of ['related_link_id','related_link_ids']) base[f]={key:`GET ${product}/promotion-links`,params:{product_id:p},query:context.roundId ? {round_id:context.roundId,status:'active'} : {status:'active'}}
    for (const f of ['recommendation']) base[f]={key:`GET ${product}/ad-recommendations`,params:{product_id:p},query:{confirm_status:'confirmed', ...(context.roundId ? {round_id:context.roundId} : {})}}
    for (const f of ['experiment_id','experiment_ids']) base[f]={key:`GET ${product}/ad-experiments`,params:{product_id:p},query:context.roundId ? {round_id:context.roundId} : {}}
    base.sku_id={key:`GET ${product}/skus`,params:{product_id:p}}
    base.competitor_id={key:`GET ${product}/competitors`,params:{product_id:p}}
    base.parent_asset_id={key:`GET ${product}/assets`,params:{product_id:p}}
    base.job_ids={key:`GET ${product}/generation-jobs`,params:{product_id:p},query:{job_status:'succeeded'}}
  }
  return base[field]
}

function LookupField({ field, value, onChange, context, reference, id }: {field:string;value:unknown;onChange:(v:unknown)=>void;context:FormContext;reference:boolean;id:string}) {
  const { user }=useSession(), [page,setPage]=useState(1), [manual,setManual]=useState(false)
  const lookup=lookupFor(field,context)
  const allowed=!!lookup && !!user && operations[lookup.key]?.roles.includes(user.role)
  const query=useQuery({queryKey:['lookup',lookup,page],enabled:allowed,queryFn:() => api<Entity[]>(lookup!.key,{params:lookup!.params,query:{...lookup!.query,page,page_size:100}})})
  const chosen=isEntity(value) ? String(value.id || '') : String(value || '')
  const rows=Array.isArray(query.data?.data) ? query.data.data : []
  if (!allowed || manual) return <div className="lookup-manual"><input id={id} value={chosen} placeholder="请输入有效编号" onChange={e => onChange(reference ? {id:e.target.value,version:isEntity(value) ? value.version : 1} : e.target.value)} />{reference && <label>版本<input aria-label="引用版本" type="number" min={1} value={isEntity(value) ? Number(value.version) || '' : ''} onChange={e => onChange({id:chosen,version:e.target.value ? Number(e.target.value) : undefined})} /></label>}{!allowed && field.includes('model') && <small>由管理员提供已配置的模型编号。</small>}{allowed && <Button variant="ghost" onClick={() => setManual(false)}>返回选择</Button>}</div>
  return <><select id={id} value={chosen} onChange={e => {const row=rows.find(r => r.id===e.target.value);onChange(row ? reference ? {id:row.id,version:row.version} : row.id : undefined)}}><option value="">{query.isPending ? '正在读取…' : '请选择'}</option>{chosen && !rows.some(r => r.id===chosen) && <option value={chosen}>当前引用 · {chosen.slice(0,8)}{isEntity(value) ? ` · v${value.version}` : ''}</option>}{rows.map(row => <option key={String(row.id)} value={String(row.id)}>{text(row.name || row.title || row.store_name || row.experiment_name || row.link_name || row.sku_name, `${stateLabel(row.asset_type || row.job_kind || '记录')} · ${String(row.id).slice(0,8)}`)}{row.version ? ` · v${row.version}` : ''}{row.status ? ` · ${stateLabel(row.status)}` : ''}</option>)}</select><div className="field-assist">{query.error ? <span>读取选项失败</span> : <span>{query.data ? `共 ${query.data.meta.total} 条` : ''}</span>}<Button variant="ghost" onClick={() => setManual(true)}>按编号填写</Button>{(query.data?.meta.total_pages || 0)>1 && <><Button variant="ghost" disabled={page===1} onClick={() => setPage(page-1)}>上一页</Button><Button variant="ghost" disabled={page >= (query.data?.meta.total_pages || 0)} onClick={() => setPage(page+1)}>下一页</Button></>}</div>{query.error && <ErrorMessage error={query.error} retry={() => void query.refetch()} />}{reference && chosen && <small>使用版本 v{isEntity(value) ? String(value.version) : '—'}，后续变更不会自动替换本次引用。</small>}</>
}

function ReviewActionPicker({value,onChange,context,id}:{value:unknown;onChange:(v:unknown)=>void;context:FormContext;id:string}){
  const {user}=useSession(),source=context.root?.source_review as Entity|undefined
  const result=useQuery({queryKey:['review-actions',context.productId,source?.id,source?.version],enabled:!!user && !!source?.id && !!context.productId,queryFn:async()=>{
    let page=1
    for(;;){const response=await api<Entity[]>('GET /products/{product_id}/resource-revisions',{params:{product_id:context.productId},query:{resource_type:'review_report',resource_id:source?.id,page,page_size:100}});const revision=response.data.find(r=>r.version===source?.version);if(revision)return revision.resource as Entity;if(page>=(response.meta.total_pages || 1))throw new Error('未找到来源复盘版本，请重新选择');page++}
  }})
  const content=result.data?.content as Entity|undefined
  const actions=Array.isArray(content?.next_actions)?content.next_actions as Entity[]:[]
  if(!actions.length)return <input id={id} value={typeof value==='string'?value:''} placeholder="填写来源复盘中的动作编号" onChange={e=>onChange(e.target.value || undefined)}/>
  return <select id={id} value={typeof value==='string'?value:''} onChange={e=>onChange(e.target.value || undefined)}><option value="">选择要采纳的优化动作</option>{actions.map(action=><option key={String(action.action_id)} value={String(action.action_id)}>{text(action.action)}</option>)}</select>
}

export function UploadField({ field, value, onChange, context, id }: {field:string;value:unknown;onChange:(v:unknown)=>void;context:FormContext;id:string}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[fileName,setFileName]=useState('')
  const {can}=useSession()
  const metadata=useQuery({queryKey:['file-metadata',value],enabled:can('GET /files/{file_id}') && typeof value==='string' && /^[0-9a-f-]{36}$/i.test(value),queryFn:()=>api<Entity>('GET /files/{file_id}',{params:{file_id:value}})})
  const isImport=context.uploadPurpose==='import'
  const needsProduct=!isImport && !context.productId
  async function upload(file?:File) {
    if (!file) return
    if (needsProduct) {setError(new Error('请先保存商品，再上传关联图片或视频'));return}
    const isVideo=file.type.startsWith('video/'), purpose=context.uploadPurpose || (isImport ? 'import' : field==='image_file_ids' ? 'product_image' : isVideo ? 'media' : 'reference')
    const max=isImport ? 10*1024*1024 : isVideo ? 500*1024*1024 : 20*1024*1024
    if (file.size>max) {setError(new Error(`文件超过${max/1024/1024} MB限制`));return}
    const data=new FormData();data.set('file',file);data.set('purpose',purpose)
    if (context.productId) data.set('product_id',context.productId)
    setBusy(true);setError(null)
    try {const result=await api<Entity>('POST /files',{body:data});onChange(result.data.id);setFileName(file.name)}catch(e){setError(e)}finally{setBusy(false)}
  }
  return <div className="file-field"><input id={id} value={text(value,'')} placeholder="上传文件或填写已有文件编号" onChange={e => onChange(e.target.value || undefined)} /><label className={`button button-secondary file-upload ${busy || needsProduct ? 'disabled' : ''}`}><FileUp size={15} />{busy ? '上传中…' : '选择文件'}<input type="file" disabled={busy || needsProduct || !can('POST /files')} accept={isImport ? '.csv,.xlsx' : 'image/jpeg,image/png,image/webp,video/mp4'} onChange={e => void upload(e.target.files?.[0])} /></label>{needsProduct && <small>先保存商品草稿，再在商品档案中上传原图。</small>}{!!(fileName || metadata.data?.data.file_name) && <small>{fileName || text(metadata.data?.data.file_name)}</small>}{!!error && <ErrorMessage error={error} />}</div>
}

function Field({ name, schema:inputSchema, value, onChange, required, context, depth=0 }: {name:string;schema:Schema;value:unknown;onChange:(v:unknown)=>void;required?:boolean;context:FormContext;depth?:number}) {
  const id=useId(), raw=resolve(inputSchema), s=nonNull(raw)
  const [variant,setVariant]=useState(0)
  const nullable=!!raw.anyOf?.some(x=>x.type==='null')
  const isRef=inputSchema.$ref?.endsWith('/ResourceRef') || raw.anyOf?.some(x=>x.$ref?.endsWith('/ResourceRef'))
  const lookup=lookupFor(name,context)
  const lookupEligible=(!!lookup && (isRef || s.format==='uuid'))
  const body=() => {
    if(name==='adopted_action_ids' && s.format==='uuid')return <ReviewActionPicker value={value} onChange={onChange} context={context} id={id}/>
    if (lookupEligible) return <LookupField field={name} value={value} onChange={onChange} context={context} reference={!!isRef} id={id} />
    if (s.oneOf) {
      const fixed=isEntity(value) && !!value.plan_type
      const choice=fixed ? s.oneOf.findIndex(x=>resolve(x).properties?.plan_type?.enum?.includes(String(value.plan_type))) : isEntity(value) && value.experiment_status ? 1 : variant
      return <>{!fixed && <div className="segmented">{s.oneOf.map((item,i)=><Button key={i} variant={i===choice?'primary':'ghost'} onClick={()=>{setVariant(i);onChange(initial(item))}}>{resolve(item).properties?.plan_type?.enum?.[0] ? stateLabel(resolve(item).properties!.plan_type.enum![0]) : i===0?'编辑计划':'变更状态'}</Button>)}</div>}<Field name="" schema={s.oneOf[Math.max(0,choice)]} value={value} onChange={onChange} context={context} depth={depth+1}/></>
    }
    if (s.type==='object') return <div className={depth?'nested-fields':'form-grid'}>{Object.entries(s.properties || {}).map(([key,child])=><Field key={key} name={key} schema={child} value={isEntity(value)?value[key]:undefined} required={s.required?.includes(key)} onChange={v=>{const next={...(isEntity(value)?value:{})};if(v===undefined)delete next[key];else next[key]=v;onChange(next)}} context={context} depth={depth+1}/>)}</div>
    if (s.type==='array') {
      const items=Array.isArray(value)?value:[]
      return <div className="array-field">{items.map((item,i)=><div className="array-item" key={i}><div className="array-index">{i+1}</div><div className="array-content"><Field name={name} schema={s.items || {type:'string'}} value={item} onChange={v=>onChange(items.map((x,j)=>j===i?v:x))} context={context} depth={depth+1}/></div><Button variant="ghost" className="icon-button" aria-label={`删除${label(name)}第${i+1}项`} onClick={()=>onChange(items.filter((_,j)=>i!==j))}><Trash2 size={14}/></Button></div>)}<Button variant="ghost" disabled={s.maxItems!==undefined && items.length>=s.maxItems} onClick={()=>onChange([...items,initial(s.items || {type:'string'})])}><Plus size={14}/>添加{label(name)}</Button>{s.minItems ? <small>至少 {s.minItems} 项</small>:null}</div>
    }
    if (['file_id','image_file_ids','reference_file_ids','main_image_file_id'].includes(name)) return <UploadField field={name} value={value} onChange={onChange} context={context} id={id}/>
    if (s.enum) return <select id={id} value={value===undefined || value===null?'':String(value)} onChange={e=>onChange(e.target.value || undefined)}><option value="">请选择</option>{s.enum.map(x=><option key={String(x)} value={String(x)}>{stateLabel(x)}</option>)}</select>
    if (s.type==='boolean') return !required && value===undefined ? <select id={id} value="" onChange={e=>onChange(e.target.value===''?undefined:e.target.value==='true')}><option value="">不提交此项</option><option value="true">开启</option><option value="false">关闭</option></select> : <label className="checkbox-field"><input id={id} type="checkbox" checked={value===true} onChange={e=>onChange(e.target.checked)}/><span>{value===true?'已开启':'未开启'}</span></label>
    if (s.type==='integer' || s.type==='number') return <input id={id} type="number" inputMode="numeric" value={typeof value==='number'?value:''} min={s.minimum} max={s.maximum} step={s.type==='integer'?1:'any'} onChange={e=>onChange(e.target.value===''?undefined:Number(e.target.value))}/>
    if (s.format==='date') return <input id={id} type="date" value={typeof value==='string'?value:''} onChange={e=>onChange(e.target.value || undefined)}/>
    if (s.format==='date-time') return <input id={id} type="datetime-local" value={typeof value==='string' && !Number.isNaN(Date.parse(value))?new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value)).replace(' ','T'):''} onChange={e=>onChange(e.target.value?new Date(e.target.value+'+08:00').toISOString():undefined)}/>
    const multiline=(s.maxLength || 0)>500 && !s.format
    return multiline?<textarea id={id} rows={3} maxLength={s.maxLength} value={typeof value==='string'?value:''} onChange={e=>onChange(e.target.value || undefined)}/>:<input id={id} type={name==='password'?'password':s.format==='uri'?'url':'text'} autoComplete={name==='password'?'new-password':'off'} inputMode={s.pattern?.includes('0-9]{2}')?'decimal':undefined} maxLength={s.maxLength} value={typeof value==='string'?value:''} placeholder={s.format==='uuid'?'有效资源编号':s.pattern?.includes('0-9]{2}')?'0.00':undefined} onChange={e=>onChange(e.target.value || undefined)}/>
  }
  const nested=s.type==='object' || s.type==='array' || !!s.oneOf
  return <div className={`form-field ${nested?'field-full':''} ${depth>1?'deep-field':''}`}>{name && <div className="field-label"><label htmlFor={id}>{label(name)}{required && <span className="required"> *</span>}</label>{!required && value!==undefined && <Button variant="ghost" onClick={()=>onChange(undefined)}>不提交</Button>}{nullable && value!==null && value!==undefined && <Button variant="ghost" onClick={()=>onChange(null)}>清空</Button>}</div>}{value===null?<div className="null-field">已设为空 <Button variant="ghost" onClick={()=>onChange(initial(s))}>重新填写</Button></div>:body()}{s.description && !nested && <small>{s.description}</small>}</div>
}

export function SchemaForm({ schemaName, value, onChange, hidden=[], context={} }: {schemaName:string;value:Entity;onChange:(value:Entity)=>void;hidden?:string[];context?:FormContext}) {
  const schema=useMemo(()=>{const s=resolve(schemas[schemaName]);if(!s.properties)return s;return {...s,properties:Object.fromEntries(Object.entries(s.properties).filter(([key])=>!hidden.includes(key)))}},[schemaName,hidden.join('|')])
  return <Field name="" schema={schema} value={value} onChange={v=>onChange(isEntity(v)?v:{})} context={{...context,root:value}}/>
}
