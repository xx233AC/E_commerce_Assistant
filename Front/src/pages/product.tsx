import { useEffect } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CirclePlus, RefreshCw } from 'lucide-react'
import { useCollection, useResource } from '../app/providers'
import { ActionButton, EditButton } from '../components/actions'
import { Badge, Button, ErrorMessage, Loading, PageHeader, SessionGate } from '../components/ui'
import { Media } from '../components/resources'
import { text } from '../lib/format'
import { ProductContext } from './product-context'
import { CatalogTab, RoundsTab } from './product-catalog'
import { DiagnosisTab, CreativeTab } from './product-ai'
import { AssetsTab, TasksTab } from './product-tasks'
import { LinksTab, AdsTab } from './product-campaigns'
import { ReviewTab } from './product-review'

const tabs=[['catalog','商品与竞品'],['rounds','运营轮次'],['diagnosis','商品诊断'],['main-image','主图方案'],['video','视频脚本'],['titles','标题方案'],['tasks','生成任务'],['assets','素材库'],['links','推广链接'],['ads','投放与实验'],['review','经营与复盘']]
export function ProductPage(){
  const {productId=''}=useParams(),[search,setSearch]=useSearchParams()
  const tab=tabs.some(([id])=>id===search.get('tab'))?search.get('tab')!:'catalog'
  const product=useResource('GET /products/{product_id}',{params:{product_id:productId}})
  const rounds=useCollection('GET /products/{product_id}/rounds',{product_id:productId},{page_size:100})
  const roundId=search.get('round') || undefined
  const roundDetail=useResource(roundId?'GET /products/{product_id}/rounds/{round_id}':null,{params:{product_id:productId,round_id:roundId}})
  const round=roundDetail.data?.data || rounds.data?.data.find(r=>r.id===roundId) || null
  function setTab(value:string){setSearch(s=>{s.set('tab',value);return s})}
  function setRound(id:string,nextTab?:string){setSearch(previous=>{const s=new URLSearchParams(previous);if(id)s.set('round',id);else s.delete('round');if(nextTab)s.set('tab',nextTab);return s})}
  useEffect(()=>{if(!roundId && rounds.data?.data.length){const first=rounds.data.data.find(r=>r.status==='active') || rounds.data.data[0];setSearch(s=>{s.set('round',String(first.id));return s},{replace:true})}},[roundId,rounds.data,setSearch])
  const p=product.data?.data
  return <><Link className="back-link" to="/products"><ArrowLeft size={14}/>返回商品列表</Link><SessionGate>{product.isPending?<Loading rows={5}/>:product.error?<ErrorMessage error={product.error} retry={()=>void product.refetch()}/>:p && <ProductContext.Provider value={{product:p,productId,round,roundId,writable:round?.status==='active',setTab,setRound}}>
    <PageHeader title={text(p.name)} description={`${text(p.category)} · 商品编号 ${productId.slice(0,8)}`} actions={<><Badge value={p.status}/><EditButton spec={{key:'PATCH /products/{product_id}',params:{product_id:productId},row:p,title:'编辑商品资料',context:{productId}}}/><Button className="icon-button" aria-label="刷新商品" onClick={()=>{void product.refetch();void rounds.refetch();if(roundId)void roundDetail.refetch()}}><RefreshCw size={15}/></Button></>}/>
    <div className="product-identity"><Media fileId={Array.isArray(p.image_file_ids)?p.image_file_ids[0]:null} className="identity-image"/><div><span>目标人群</span><strong>{text(p.target_audience)}</strong></div><div className="identity-selling"><span>核心卖点</span><div>{Array.isArray(p.selling_points)?p.selling_points.map((v,i)=><span className="tag" key={i}>{String(v)}</span>):'—'}</div></div></div>
    <div className="round-bar"><div className="round-selector"><label htmlFor="current-round">运营轮次</label><select id="current-round" value={roundId || ''} onChange={e=>setRound(e.target.value)}><option value="">{rounds.isPending?'正在读取…':'尚未创建轮次'}</option>{roundId && !rounds.data?.data.some(r=>r.id===roundId) && round && <option value={roundId}>{text(round.name)}</option>}{rounds.data?.data.map(r=><option key={String(r.id)} value={String(r.id)}>{text(r.name)}</option>)}</select>{round && <Badge value={round.status}/>}</div><div className="inline-actions">{!!round?.objective && <span className="round-objective" title={String(round.objective)}>{String(round.objective)}</span>}<ActionButton spec={{key:'POST /products/{product_id}/rounds',title:'新建运营轮次',params:{product_id:productId},context:{productId},onSuccess:data=>{if(data && typeof data==='object' && 'id'in data){setRound(String(data.id),'diagnosis')}}}} disabled={p.status!=='active' || rounds.data?.data.some(r=>r.status==='active')} title={p.status!=='active'?'请先启用商品':rounds.data?.data.some(r=>r.status==='active')?'请先完成当前轮次':undefined}><CirclePlus size={15}/>新建轮次</ActionButton></div></div>
    {rounds.error && <ErrorMessage error={rounds.error} retry={()=>void rounds.refetch()}/>}{roundDetail.error && <ErrorMessage error={roundDetail.error} retry={()=>void roundDetail.refetch()}/>}
    <div className="tabs product-tabs" role="tablist" aria-label="商品运营环节">{tabs.map(([id,name])=><button key={id} role="tab" aria-selected={tab===id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{name}</button>)}</div>
    <div className="product-tab-content" key={tab}>{tab==='catalog'?<CatalogTab/>:tab==='rounds'?<RoundsTab/>:tab==='diagnosis'?<DiagnosisTab/>:tab==='main-image'?<CreativeTab kind="main_image"/>:tab==='video'?<CreativeTab kind="video_script"/>:tab==='titles'?<CreativeTab kind="title"/>:tab==='tasks'?<TasksTab/>:tab==='assets'?<AssetsTab/>:tab==='links'?<LinksTab/>:tab==='ads'?<AdsTab/>:<ReviewTab/>}</div>
  </ProductContext.Provider>}</SessionGate></>
}
