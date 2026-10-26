import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Plus, Search } from 'lucide-react'
import { useCollection, useSession } from '../app/providers'
import { ActionButton, EditButton } from '../components/actions'
import { Media, ResourceList } from '../components/resources'
import { PageHeader } from '../components/ui'
import { money, text } from '../lib/format'

export function ProductsPage(){
  const [keyword,setKeyword]=useState(''),[search,setSearch]=useState(''),[status,setStatus]=useState('')
  const store=useCollection('GET /stores'),shop=store.data?.data[0],navigate=useNavigate(),{user}=useSession()
  useEffect(()=>{const timer=setTimeout(()=>setSearch(keyword),300);return()=>clearTimeout(timer)},[keyword])
  const create={key:'POST /products',title:'新增商品',description:'先保存商品草稿，再补充 SKU 和商品原图。',initial:{status:'draft',...(shop?{store_id:shop.id}:{})},hidden:['status','image_file_ids',...(shop?['store_id']:[])],onSuccess:(data:unknown)=>{if(data && typeof data==='object' && 'id' in data)navigate(`/products/${String(data.id)}`)}}
  return <><PageHeader title="商品运营" description="一个商品，一份完整档案；每一轮优化都有迹可循。" actions={<><Link className="button button-secondary" to="/imports">批量导入</Link><ActionButton spec={create} variant="primary" disabled={!shop} title={!shop?'请先创建店铺':undefined}><Plus size={15}/>新增商品</ActionButton></>}/>
    <div className="tabs status-tabs" role="tablist" aria-label="商品状态">{[['','全部商品'],['draft','草稿'],['active','已启用'],['inactive','已停用']].map(([key,name])=><button role="tab" aria-selected={status===key} className={status===key?'active':''} key={key} onClick={()=>setStatus(key)}>{name}</button>)}</div>
    <ResourceList title="商品档案" apiKey="GET /products" query={{keyword:search,status}} filters={<><div className="search-field"><Search size={16}/><input aria-label="搜索商品" value={keyword} onChange={e=>setKeyword(e.target.value)} placeholder="搜索商品名称或关键词"/></div>{user && !shop && !store.isPending && <Link className="text-link" to="/store">先设置店铺<ArrowRight size={13}/></Link>}</>} columns={[
      {key:'name',label:'商品',render:r=><div className="product-cell"><Media fileId={Array.isArray(r.image_file_ids)?r.image_file_ids[0]:null} className="product-thumbnail"/><div><Link className="text-link product-name" to={`/products/${r.id}`}>{text(r.name)}</Link><small>{text(r.category)} · {text(r.id).slice(0,8)}</small></div></div>},
      {key:'price',label:'售价 / 成本',numeric:true,render:r=><div className="stacked-number"><span>{money(r.price)}</span><small>{money(r.cost)}</small></div>},
      {key:'status'},{key:'last_diagnosis_at',label:'最近诊断'},{key:'last_review_at',label:'最近复盘'},
    ]} canOpen={false} rowActions={r=><><Link className="button button-ghost" to={`/products/${r.id}`}>进入运营<ArrowRight size={13}/></Link><EditButton spec={{key:'PATCH /products/{product_id}',params:{product_id:r.id},row:r,title:'编辑商品',context:{productId:String(r.id)}}}/></>} emptyText="还没有商品" description="先录入商品资料、SKU 与原图，再开始诊断和创意制作。" emptyAction={<ActionButton spec={create} disabled={!shop}><Plus size={14}/>新增第一个商品</ActionButton>}/>
  </>
}
