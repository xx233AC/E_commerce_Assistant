import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Check } from 'lucide-react'
import { api, operations } from '../api/client'
import type { Entity } from '../api/types'
import { useNotice, useSession } from '../app/providers'
import { isEntity } from '../lib/format'
import { Button, Dialog, ErrorMessage, RecordView } from './ui'
import { editable, initial, schemas, SchemaForm, validateBody } from './schema-form'
import type { FormContext } from './schema-form'
import type { ActionSpec } from './actions'

export default function ActionDialog({spec,onClose}:{spec:ActionSpec;onClose:()=>void}) {
  const operation=operations[spec.key], schemaName=spec.schema || operation.body
  const [value,setValue]=useState<Entity>(()=>({...(schemaName ? initial(schemas[schemaName]) as Entity : {}),...(schemaName && spec.row ? editable(schemaName,spec.row) : {}),...spec.initial}))
  const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[validation,setValidation]=useState<string[]>([]),[result,setResult]=useState<unknown>(undefined)
  const client=useQueryClient(),notice=useNotice(),{can}=useSession()
  const idempotency=useRef({fingerprint:'',key:crypto.randomUUID()})
  const productId=String(value.product_id || spec.params?.product_id || spec.context?.productId || '') || undefined
  const context:FormContext={...spec.context,productId,roundId:String(value.round_id || spec.context?.roundId || '') || undefined,...(['ImportCreate','PerformanceImportCreate'].includes(operation.body || '')?{uploadPurpose:'import'}:operation.body==='AssetCreate'?{uploadPurpose:'media'}:{})}
  const version=spec.version ?? spec.row?.version
  async function submit(e:React.FormEvent) {
    e.preventDefault();setError(null)
    if (!can(spec.key)) {setError(new Error('当前角色没有执行此操作的权限'));return}
    const errors=operation.body?validateBody(operation.body,value):[]
    if(errors.length){setValidation([...new Set(errors)]);return}
    setValidation([]);setBusy(true)
    const fingerprint=JSON.stringify(value)
    if(idempotency.current.fingerprint!==fingerprint)idempotency.current={fingerprint,key:crypto.randomUUID()}
    try {
      const response=await api(spec.key,{params:spec.params,body:operation.body?value:undefined,version,idempotencyKey:idempotency.current.key})
      await client.invalidateQueries({queryKey:['api']});await client.invalidateQueries({queryKey:['lookup']})
      const async=isEntity(response.data) && ('job' in response.data || 'import_batch' in response.data)
      notice(async?'已提交，请在任务或导入记录中查看进度':'操作已完成')
      spec.onSuccess?.(response.data)
      if(spec.showResult)setResult(response.data);else onClose()
    } catch(e){setError(e)}finally{setBusy(false)}
  }
  return <Dialog title={spec.title || operation.title} onClose={onClose} busy={busy} wide={!!schemaName && ['CreativePlanPatch','DiagnosisPatch','AdRecommendationPatch','ReviewPatch','ModelConfigCreate'].includes(schemaName)}>{result!==undefined?<><div className="dialog-body"><div className="inline-notice"><Check size={16}/>操作已完成</div>{isEntity(result)?<RecordView data={result}/>:<p>{JSON.stringify(result)}</p>}</div><footer className="dialog-footer"><Button variant="primary" onClick={onClose}>完成</Button></footer></>:<form onSubmit={e=>void submit(e)} noValidate><div className="dialog-body">{spec.description && <p className={`form-intro ${spec.danger?'danger-text':''}`}>{spec.description}</p>}{schemaName?<SchemaForm schemaName={schemaName} value={value} onChange={setValue} hidden={spec.hidden} context={context}/>:<p>确认{spec.title || operation.title}？</p>}{validation.length>0 && <div className="validation-box" role="alert"><strong>请检查以下内容</strong><ul>{validation.map((s,i)=><li key={i}>{s}</li>)}</ul></div>}{!!error && <ErrorMessage error={error}/>}</div><footer className="dialog-footer"><span>{operation.concurrency && version ? `基于版本 v${version}`:''}</span><Button disabled={busy} onClick={onClose}>取消</Button><Button type="submit" loading={busy} variant={spec.danger?'danger':'primary'} disabled={!can(spec.key)}>{busy?'提交中…':spec.danger?'确认操作':'确认提交'}{!busy && <ArrowRight size={14}/>}</Button></footer></form>}</Dialog>
}
