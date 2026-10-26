import { Component, lazy, StrictMode, Suspense } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import type { Root } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import './styles.css'
import { Providers } from './app/providers'
import { Layout } from './app/layout'
import { ActionProvider } from './components/actions'
import { Button, Empty, Loading, PageHeader } from './components/ui'

const LoginPage=lazy(()=>import('./pages/login').then(m=>({default:m.LoginPage})))
const DashboardPage=lazy(()=>import('./pages/dashboard').then(m=>({default:m.DashboardPage})))
const ProductsPage=lazy(()=>import('./pages/products').then(m=>({default:m.ProductsPage})))
const ProductPage=lazy(()=>import('./pages/product').then(m=>({default:m.ProductPage})))
const ImportsPage=lazy(()=>import('./pages/imports').then(m=>({default:m.ImportsPage})))
const StorePage=lazy(()=>import('./pages/management').then(m=>({default:m.StorePage})))
const InventoryPage=lazy(()=>import('./pages/management').then(m=>({default:m.InventoryPage})))
const UsersPage=lazy(()=>import('./pages/management').then(m=>({default:m.UsersPage})))
const SettingsPage=lazy(()=>import('./pages/management').then(m=>({default:m.SettingsPage})))
const AuditPage=lazy(()=>import('./pages/management').then(m=>({default:m.AuditPage})))
const GuidePage=lazy(()=>import('./pages/management').then(m=>({default:m.GuidePage})))

class ErrorBoundary extends Component<{children:ReactNode},{error:Error|null}>{
  state:{error:Error|null}={error:null}
  static getDerivedStateFromError(error:Error){return {error}}
  componentDidCatch(error:Error,info:ErrorInfo){console.error('页面异常',error.message,info.componentStack)}
  render(){return this.state.error?<div className="app-error"><h1>页面暂时无法显示</h1><p>请刷新页面重新加载，已提交的业务操作请先查询结果。</p><Button onClick={()=>window.location.reload()}>重新加载</Button></div>:this.props.children}
}

const root=(import.meta.hot?.data.reactRoot as Root|undefined) || createRoot(document.getElementById('root')!)
if(import.meta.hot){
  import.meta.hot.data.reactRoot=root
  // 公共Context/Hook模块不能作为Fast Refresh边界时，完整刷新以保持身份一致。
  import.meta.hot.accept(()=>window.location.reload())
}
root.render(<StrictMode><ErrorBoundary><Providers><BrowserRouter><ActionProvider><Suspense fallback={<Loading rows={5}/>}><Routes><Route path="/login" element={<LoginPage/>}/><Route path="/" element={<Layout/>}><Route index element={<DashboardPage/>}/><Route path="products" element={<ProductsPage/>}/><Route path="products/:productId" element={<ProductPage/>}/><Route path="inventory" element={<InventoryPage/>}/><Route path="imports" element={<ImportsPage/>}/><Route path="store" element={<StorePage/>}/><Route path="users" element={<UsersPage/>}/><Route path="settings" element={<SettingsPage/>}/><Route path="audit" element={<AuditPage/>}/><Route path="guide" element={<GuidePage/>}/><Route path="*" element={<><PageHeader title="页面不存在"/><Empty title="没有找到此页面" description="请通过左侧导航选择要访问的功能。"/></>}/></Route></Routes></Suspense></ActionProvider></BrowserRouter></Providers></ErrorBoundary></StrictMode>)
