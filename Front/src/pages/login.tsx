import { useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { Brand } from '../app/layout'
import { useSession } from '../app/providers'
import { Button, ErrorMessage } from '../components/ui'

export function LoginPage(){
  const {user,login}=useSession(),[search]=useSearchParams()
  const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[visible,setVisible]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null)
  const next=search.get('next') || '/'
  const safeNext=next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login')?next:'/'
  if(user)return <Navigate to={safeNext} replace/>
  return <main className="login-layout"><section className="login-story"><Brand/><div className="login-copy"><div className="small-kicker">让每一轮运营有据可循</div><h1>从商品洞察，<br/>走向下一轮增长。</h1><p>把诊断、创意、投放与复盘放在同一个工作空间，清楚知道每个商品下一步该做什么。</p><div className="login-process"><span>商品诊断</span><ArrowRight size={15}/><span>内容创意</span><ArrowRight size={15}/><span>投放与复盘</span></div></div><div className="login-story-footer"><span>单店铺 · 三类角色 · 完整运营闭环</span><span>电商运营助手</span></div></section><section className="login-form-area"><Link to="/" className="back-link"><ArrowLeft size={15}/>返回工作台</Link><div className="login-form-wrap"><LockKeyhole size={24} strokeWidth={1.5}/><h2>登录工作空间</h2><p>使用店铺管理员分配的账号登录。</p><form onSubmit={e=>{e.preventDefault();const data=new FormData(e.currentTarget);setBusy(true);setError(null);void login(String(data.get('username') || '').trim(),String(data.get('password') || '')).catch(setError).finally(()=>setBusy(false))}}><div className="form-field"><label htmlFor="username">用户名</label><input id="username" name="username" autoComplete="username" required minLength={3} value={username} onChange={e=>setUsername(e.target.value)} placeholder="输入用户名" autoFocus/></div><div className="form-field"><label htmlFor="password">密码</label><div className="password-field"><input id="password" name="password" type={visible?'text':'password'} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="输入密码"/><Button variant="ghost" className="icon-button" aria-label={visible?'隐藏密码':'显示密码'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={16}/>:<Eye size={16}/>}</Button></div></div>{!!error && <ErrorMessage error={error}/>}<Button type="submit" variant="primary" loading={busy}>登录<ArrowRight size={15}/></Button></form><small className="login-note">账号或密码有问题？请联系店铺管理员。</small></div><footer className="login-form-footer">商品有档案，决策有依据，优化有回路。</footer></section></main>
}
