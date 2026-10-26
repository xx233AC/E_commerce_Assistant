import { createContext, lazy, Suspense, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Pencil, Plus } from 'lucide-react'
import { operations } from '../api/client'
import type { Entity } from '../api/types'
import { useSession } from '../app/providers'
import { Button, Dialog, Loading } from './ui'
import type { FormContext } from './schema-form'

export interface ActionSpec {
  key: string; title?: string; params?: Entity; row?: Entity; version?: number;
  initial?: Entity; hidden?: string[]; schema?: string; context?: FormContext;
  description?: string; danger?: boolean; onSuccess?: (data: unknown) => void;
  showResult?: boolean;
}
const ActionDialog=lazy(()=>import('./action-dialog'))
const ActionContext=createContext<(spec:ActionSpec)=>void>(()=>{})
export const useAction=()=>useContext(ActionContext)

export function ActionProvider({children}:{children:ReactNode}) {
  const [current,setCurrent]=useState<{id:string;spec:ActionSpec}|null>(null)
  return <ActionContext.Provider value={spec=>setCurrent({id:crypto.randomUUID(),spec})}>{children}{current && <Suspense fallback={<Dialog title={current.spec.title || '正在载入表单'} onClose={()=>setCurrent(null)}><div className="dialog-body"><Loading/></div></Dialog>}><ActionDialog key={current.id} spec={current.spec} onClose={()=>setCurrent(null)}/></Suspense>}</ActionContext.Provider>
}
export function ActionButton({spec,children,variant='secondary',disabled,title}:{spec:ActionSpec;children?:ReactNode;variant?:'primary'|'secondary'|'ghost'|'danger';disabled?:boolean;title?:string}) {
  const open=useAction(),{can}=useSession()
  const allowed=can(spec.key)
  if(!allowed)return null
  return <Button variant={variant} disabled={disabled} title={title} onClick={()=>open(spec)}>{children || <><Plus size={14}/>{spec.title || operations[spec.key]?.title}</>}</Button>
}
export function EditButton({spec,disabled}:{spec:ActionSpec;disabled?:boolean}) { return <ActionButton spec={spec} variant="ghost" disabled={disabled}><Pencil size={14}/>编辑</ActionButton> }

export function useActionDefaults(productId:string,roundId?:string) {
  return useMemo(()=>({params:{product_id:productId},context:{productId,roundId},...(roundId?{initial:{round_id:roundId},hidden:['round_id']}:{})}),[productId,roundId])
}
