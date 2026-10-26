import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ImageOff, Plus, RefreshCw } from 'lucide-react'
import type { Entity } from '../api/types'
import { useCollection, useResource, useSession } from '../app/providers'
import { ActionButton } from './actions'
import type { ActionSpec } from './actions'
import { Button, DataTable, Dialog, Empty, ErrorMessage, Loading, Pagination, Panel, RecordView, SessionGate } from './ui'
import type { Column } from './ui'

export function Media({ fileId, type='image', className='' }:{fileId:unknown;type?:string;className?:string}) {
  const result=useResource<{url:string}>((typeof fileId==='string' && fileId)?'GET /files/{file_id}/access-url':null,{params:{file_id:fileId}})
  if (!result.data || result.error) return <div className={`media-placeholder ${className}`} title={result.error?'预览暂不可用':'未上传图片'}><ImageOff size={20} strokeWidth={1.4}/></div>
  return type==='video'?<video className={`asset-preview ${className}`} src={result.data.data.url} controls preload="metadata" aria-label="视频素材预览"/>:<img className={`asset-preview ${className}`} src={result.data.data.url} alt="商品素材" loading="lazy" onError={e=>{e.currentTarget.alt='素材暂不可用'}}/>
}

export function ResourceDetail({row,title,detailKey,params,onClose,children}:{row:Entity;title:string;detailKey?:string;params?:Entity;onClose:()=>void;children?:ReactNode}) {
  const result=useResource(detailKey || null,{params})
  return <Dialog title={title} onClose={onClose} wide><div className="dialog-body">{children}{detailKey && result.isPending?<Loading/>:result.error?<ErrorMessage error={result.error} retry={()=>void result.refetch()}/>:<RecordView data={result.data?.data || row}/>}</div><footer className="dialog-footer"><Button onClick={onClose}>关闭</Button></footer></Dialog>
}

export function ResourceList({title,description,apiKey,params={},query={},columns,create,rowActions,detailKey,detailParam,renderDetail,headerActions,poll=false,filters,emptyText,emptyAction,compact=false,canOpen=true}:{
  title:string;description?:string;apiKey:string;params?:Entity;query?:Entity;columns:Column[];create?:ActionSpec;
  rowActions?:(row:Entity)=>ReactNode;detailKey?:string;detailParam?:string;renderDetail?:(row:Entity,onClose:()=>void)=>ReactNode;headerActions?:ReactNode;poll?:boolean;filters?:ReactNode;emptyText?:string;emptyAction?:ReactNode;compact?:boolean;canOpen?:boolean;
}) {
  const [page,setPage]=useState(1),[selected,setSelected]=useState<Entity|null>(null)
  const {can}=useSession()
  const filterSignature=JSON.stringify({apiKey,params,query})
  useEffect(()=>setPage(1),[filterSignature])
  const result=useCollection(apiKey,params,{...query,page,page_size:compact?5:20},poll)
  return <Panel title={title} description={description} actions={<div className="inline-actions">{headerActions}{create && <ActionButton spec={create} variant="secondary"><Plus size={14}/>{create.title || '新增'}</ActionButton>}<Button disabled={!can(apiKey)} className="icon-button" variant="ghost" title="刷新" aria-label={`刷新${title}`} onClick={()=>void result.refetch()}><RefreshCw size={15} className={result.isFetching?'spin':''}/></Button></div>}>
    <SessionGate>{filters && <div className="list-filters">{filters}</div>}{result.isPending?<Loading/>:result.error?<ErrorMessage error={result.error} retry={()=>void result.refetch()}/>:<><DataTable rows={result.data?.data || []} columns={columns} actions={rowActions} onOpen={canOpen ? row=>setSelected(row) : undefined} empty={<Empty title={emptyText || `暂无${title}`} description={description} action={emptyAction}/>}/>{!compact && <Pagination meta={result.data?.meta} page={page} onChange={setPage}/>}</>}</SessionGate>
    {selected && (renderDetail ? renderDetail(selected,()=>setSelected(null)) : <ResourceDetail row={selected} title={`${title}详情`} detailKey={detailKey} params={{...params,...(detailParam?{[detailParam]:selected[detailParam] || selected.id}:{})}} onClose={()=>setSelected(null)}/>)}
  </Panel>
}
