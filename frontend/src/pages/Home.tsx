import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import type { StatsOverview } from '../lib/types'
import { useAuth } from '../store/auth'
import Icon from '../components/Icon'
export default function Home(){
 const [todayTotal,setTodayTotal]=useState<number|null>(null)
 const [stats,setStats]=useState<StatsOverview|null>(null)
 const [error,setError]=useState(false)
 const [retry,setRetry]=useState(0)
 const user=useAuth(s=>s.user)
 useEffect(()=>{setError(false);void Promise.all([api.get('/review/today',{params:{limit:1}}).then(r=>setTodayTotal(r.data.total)),api.get('/stats/overview').then(r=>setStats(r.data))]).catch(()=>setError(true))},[retry])
 return <div><span className="page-kicker">YOUR LEARNING SPACE</span><div className="dashboard-heading"><div><h1>你好，{user?.nickname||'学习者'}。</h1><p>给知识一点时间，也给自己一点进步。</p></div><Link to="/documents" className="ml-btn"><Icon name="upload" size={15}/> 上传新资料</Link></div>{error&&<div className="app-error" role="alert">学习数据暂时无法加载，请确认后端服务已启动。 <button onClick={()=>setRetry(r=>r+1)} className="underline">重试</button></div>}<section className="dashboard-focus"><div><span className="focus-kicker"><Icon name="loop" size={15}/> 今日学习计划</span><h2>{todayTotal===null?(error?'稍后再试，学习不着急。':'正在准备你的复习…'):todayTotal>0?'让昨天的知识，留在明天。':'今日复习，已经完成。'}</h2><p>{todayTotal===null?'连接学习空间后，即可查看你的复习安排。':todayTotal>0?`今天有 ${todayTotal} 个知识点等待巩固。用一次主动回忆，让记忆更稳固。`:'可以上传新的学习资料，继续拓展你的知识边界。'}</p><Link to={todayTotal&&todayTotal>0?'/review':'/documents'} className="ml-btn ml-btn-primary">{todayTotal&&todayTotal>0?'开始今日复习':'探索我的知识库'} <Icon name="arrow" size={17}/></Link></div><div className="focus-orbit" aria-hidden="true"><div><strong>{todayTotal??'—'}</strong><span>张卡片</span></div><Icon name="spark" size={28}/></div></section><section className="dashboard-metrics">{[{icon:'file',label:'知识点总数',value:stats?String(stats.kp_total):'—',link:'/documents',hint:'持续积累'},{icon:'loop',label:'平均记忆保有率',value:stats?`${Math.round(stats.retention.avg_retrievability*100)}%`:'—',link:'/stats',hint:'巩固记忆'},{icon:'chat',label:'需要关注的错因',value:stats?.error_top[0]?.tag??'暂无',link:'/stats',hint:'理解更深入'}].map(c=><Link to={c.link} className="metric-card" key={c.label}><div className="metric-top"><Icon name={c.icon as 'file'} size={21}/><span>{c.hint} ↗</span></div><strong>{c.value}</strong><small>{c.label}</small></Link>)}</section><section className="dashboard-guide"><h2>让学习，形成自己的节奏。</h2><div className="guide-grid">{[{to:'/documents',title:'从一份资料开始',text:'上传课件，建立自己的知识库。'},{to:'/review',title:'记得住，也讲得明白',text:'在递进练习中，让理解更扎实。'},{to:'/stats',title:'回看你的成长轨迹',text:'发现薄弱处，把精力用在需要的地方。'}].map((c,i)=><Link to={c.to} key={c.title}><span>0{i+1} ↗</span><h3>{c.title}</h3><p>{c.text}</p></Link>)}</div></section></div>
}
