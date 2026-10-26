import { Link } from 'react-router-dom'
import { ArrowRight, CircleCheck, ClipboardCheck, FileImage, Package, Plus, RefreshCw } from 'lucide-react'
import type { Entity } from '../api/types'
import { useResource } from '../app/providers'
import { ActionButton } from '../components/actions'
import { Badge, Button, DataTable, Empty, ErrorMessage, Loading, PageHeader, Panel, SessionGate } from '../components/ui'
import { count, text } from '../lib/format'

const stages=[['建档','商品、SKU 与竞品'],['诊断','明确定位与卖点'],['创意','主图、脚本与标题'],['审核','检查素材与文案'],['投放','人工确认与实验'],['复盘','数据回填与优化']]
export function DashboardPage(){
  const result=useResource<Entity>('GET /workspace/dashboard')
  const d=result.data?.data,store=d?.store as Entity|undefined
  return <><PageHeader title="工作台" description="聚焦待办，推进每个商品的下一轮优化。" actions={<><Button onClick={()=>void result.refetch()}><RefreshCw size={15} className={result.isFetching?'spin':''}/>刷新</Button><Link className="button button-primary" to="/products"><Package size={15}/>进入商品运营</Link></>}/><SessionGate>
    {result.isPending?<Loading rows={4}/>:result.error?<ErrorMessage error={result.error} retry={()=>void result.refetch()}/>:<>
      <section className="overview-strip" aria-label="经营工作概览">{[['商品总数',d?.product_count],['启用商品',d?.active_product_count],['库存预警',d?.low_stock_sku_count],['运行中任务',d?.running_job_count]].map(([name,value])=><div key={String(name)}><span>{String(name)}</span><strong className="num">{count(value)}</strong></div>)}</section>
      {!store && <div className="setup-banner"><div><h2>先设置你的店铺</h2><p>完成店铺信息后，就可以为第一个商品建立档案。</p></div><ActionButton spec={{key:'POST /stores',title:'创建店铺'}} variant="primary"><Plus size={15}/>创建店铺</ActionButton></div>}
      <div className="dashboard-grid"><Panel title="需要你处理" description="人工确认是运营闭环中的关键一步。"><Link className="attention-row" to="/products"><FileImage size={19}/><div><strong>素材待审核</strong><small>检查生成结果，再用于本轮投放</small></div><strong className="num">{count(d?.pending_asset_review_count)}</strong><ArrowRight size={16}/></Link><Link className="attention-row" to="/products"><ClipboardCheck size={19}/><div><strong>投放建议待确认</strong><small>核对预算、人群与素材</small></div><strong className="num">{count(d?.pending_ad_confirmation_count)}</strong><ArrowRight size={16}/></Link><Link className="attention-row" to="/inventory"><Package size={19}/><div><strong>库存预警</strong><small>检查可用库存与预警阈值</small></div><strong className="num">{count(d?.low_stock_sku_count)}</strong><ArrowRight size={16}/></Link></Panel>
      <Panel title="店铺概况" actions={<Link className="text-link" to="/store">查看店铺<ArrowRight size={13}/></Link>}>{store?<><div className="store-summary"><span className="store-initial">{text(store.store_name).slice(0,1)}</span><div><h3>{text(store.store_name)}</h3><Badge value={store.platform}/></div></div><dl className="simple-pairs"><div><dt>负责人</dt><dd>{text(store.owner_name)}</dd></div><div><dt>经营范围</dt><dd>单店铺</dd></div><div><dt>统计时区</dt><dd>北京时间 UTC+8</dd></div></dl></>:<Empty title="尚未创建店铺" description="店铺信息将与商品和经营数据关联。"/>}</Panel></div>
      <Panel title="最近运营轮次" actions={<Link className="text-link" to="/products">查看全部商品<ArrowRight size={13}/></Link>}><DataTable rows={Array.isArray(d?.latest_rounds)?d.latest_rounds as Entity[]:[]} columns={[{key:'name',label:'运营轮次',render:r=><Link className="text-link" to={`/products/${r.product_id}?tab=rounds`}>{text(r.name)}</Link>},{key:'objective',label:'本轮目标'},{key:'stage',label:'当前环节'},{key:'status'},{key:'updated_at'}]} empty={<Empty title="还没有运营轮次" description="建立商品档案后，创建第一轮运营目标。" action={<Link className="button button-secondary" to="/products">前往商品运营<ArrowRight size={14}/></Link>}/>}/></Panel>
    </>}
  </SessionGate><Panel title="单品运营路径" description="每轮保留独立的版本、素材和数据，复盘后再开始下一轮。" className="workflow-panel"><ol className="workflow-line">{stages.map(([name,description],i)=><li key={name}><span className="workflow-step">{i===stages.length-1?<CircleCheck size={16}/>:String(i+1).padStart(2,'0')}</span><strong>{name}</strong><small>{description}</small></li>)}</ol></Panel></>
}
