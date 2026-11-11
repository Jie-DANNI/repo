import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import Brand from './Brand'
import Icon from './Icon'
const NAV = [{to:'/workspace',label:'学习工作台',icon:'home'},{to:'/documents',label:'我的知识库',icon:'file'},{to:'/review',label:'今日复习',icon:'loop'},{to:'/stats',label:'学习画像',icon:'chart'}] as const
export default function Layout(){
 const {user,logout}=useAuth(); const navigate=useNavigate(); const location=useLocation()
 const active=NAV.find(n=>n.to===location.pathname)
 return <div className="workspace"><aside className="workspace-sidebar"><Brand/><p>我的学习空间</p><nav aria-label="学习空间导航">{NAV.map(n=><NavLink key={n.to} to={n.to} className={({isActive})=>`ml-nav-link ${isActive?'is-active':''}`}><Icon name={n.icon}/>{n.label}</NavLink>)}</nav><div className="sidebar-tip"><Icon name="spark"/><h3>每天一点，记得更久。</h3><p>主动回忆，再回看资料。<br/>让复习成为一次新的理解。</p><NavLink to="/demo">了解学习流程 <Icon name="arrow" size={14}/></NavLink></div><div className="sidebar-profile"><span className="mini-avatar">{user?.nickname?.slice(0,1)||'M'}</span><div><strong>{user?.nickname||'学习者'}</strong><small>{user?.role==='demo'?'演示账号':'我的学习空间'}</small></div><button aria-label="退出登录" title="退出登录" onClick={()=>{logout();navigate('/',{replace:true})}}><Icon name="logout" size={18}/></button></div></aside><div className="workspace-main"><header className="workspace-topbar"><span>我的空间 &nbsp; / &nbsp; {active?.label||'学习'}</span><div><span><i className="live-dot"/> 每一次学习，都有收获</span><NavLink to="/documents" className="ml-btn"><Icon name="upload" size={14}/> 上传资料</NavLink></div></header><main className="workspace-content"><Outlet/></main><footer className="workspace-footer">MemoLoop 忆循环 · 学会，也记得。</footer></div></div>
}
