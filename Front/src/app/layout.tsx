import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ArrowUpRight, BookOpenCheck, ChevronRight, CircleHelp, CloudUpload, LayoutDashboard, LogOut, Menu, Package, Settings2, ShoppingBag, Store, Users, X } from 'lucide-react'
import { useCollection, useNotice, useSession } from './providers'
import { Button } from '../components/ui'
import { stateLabel } from '../lib/labels'

const nav=[{to:'/',name:'工作台',icon:LayoutDashboard},{to:'/products',name:'商品运营',icon:Package},{to:'/inventory',name:'SKU 与库存',icon:ShoppingBag},{to:'/imports',name:'导入中心',icon:CloudUpload},{to:'/store',name:'店铺设置',icon:Store}]
const adminNav=[{to:'/users',name:'用户管理',icon:Users},{to:'/settings',name:'系统设置',icon:Settings2},{to:'/audit',name:'操作记录',icon:BookOpenCheck}]
export function Brand(){return <div className="brand"><svg width="30" height="34" viewBox="0 0 32 36" fill="none" aria-hidden="true"><path d="M5 11h22l-2 20H7L5 11Zm6 0V8a5 5 0 0 1 10 0v3M11 20l4 4 7-8" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round"/></svg><div><strong>电商运营助手</strong><small>商品运营工作台</small></div></div>}
export function Layout(){
  const [mobile,setMobile]=useState(false),[compact,setCompact]=useState(()=>window.matchMedia('(max-width:1050px)').matches),{user,logout}=useSession(),navigate=useNavigate(),location=useLocation(),notice=useNotice()
  const stores=useCollection('GET /stores')
  const shop=stores.data?.data[0]
  useEffect(()=>{setMobile(false)},[location.pathname])
  useEffect(()=>{const media=window.matchMedia('(max-width:1050px)');const change=()=>setCompact(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change)},[])
  return <div className="app-frame"><a href="#main-content" className="skip-link">跳到主要内容</a>{mobile && <button className="nav-scrim" aria-label="关闭菜单遮罩" onClick={()=>setMobile(false)}/>}
    <aside id="app-navigation" inert={compact && !mobile} className={`sidebar ${mobile?'sidebar-open':''}`} aria-label="主导航"><div className="brand-row"><Brand/><Button className="mobile-only icon-button" variant="ghost" aria-label="关闭导航" onClick={()=>setMobile(false)}><X size={18}/></Button></div>
      <div className="workspace-scope"><span className="scope-dot"/><div><strong>{shop ? String(shop.store_name) : stores.isError?'店铺暂不可用':user?'尚未设置店铺':'单店铺工作空间'}</strong><small>{shop?stateLabel(shop.platform):'从一个商品开始优化'}</small></div></div>
      <div className="nav-group-label">运营空间</div><nav>{nav.map(({to,name,icon:Icon})=><NavLink key={to} to={to} end={to==='/'}><Icon size={17} strokeWidth={1.7}/><span>{name}</span></NavLink>)}</nav>
      {(!user || user.role==='admin') && <><div className="nav-group-label">管理</div><nav>{adminNav.map(({to,name,icon:Icon})=><NavLink key={to} to={to}><Icon size={17} strokeWidth={1.7}/><span>{name}</span></NavLink>)}</nav></>}
      <div className="sidebar-bottom"><NavLink className="help-link" to="/guide"><CircleHelp size={16}/>使用指引<ArrowUpRight size={13}/></NavLink><div className="user-row"><div className="avatar">{user?.display_name?.slice(0,1) || '访'}</div><div><strong>{user?.display_name || '尚未登录'}</strong><small>{user?stateLabel(user.role):'登录后访问店铺'}</small></div>{user?<Button className="icon-button" variant="ghost" aria-label="退出登录" onClick={()=>{void logout().catch(()=>notice('已清理本地登录状态','error')).finally(()=>navigate('/login'))}}><LogOut size={16}/></Button>:<Button className="icon-button" variant="ghost" aria-label="前往登录" onClick={()=>navigate('/login')}><ChevronRight size={17}/></Button>}</div></div>
    </aside>
    <div className="workspace-main"><div className="topbar"><div className="topbar-location"><Button variant="ghost" className="mobile-only icon-button" aria-label="打开导航" aria-expanded={mobile} aria-controls="app-navigation" onClick={()=>setMobile(true)}><Menu size={19}/></Button><span>运营工作空间</span><ChevronRight size={13}/><strong>{[...nav,...adminNav].find(n=>n.to==='/'?location.pathname==='/':location.pathname.startsWith(n.to))?.name || (location.pathname==='/guide'?'使用指引':'商品工作区')}</strong></div><div className="topbar-right"><span className="timezone">北京时间 · UTC+8</span><span className={`connection-dot ${user?'connected':''}`}/><span>{user?'已登录':'待登录'}</span></div></div><main id="main-content" className="workspace-sheet"><Outlet/></main></div>
  </div>
}
