import { useState } from 'react'
import Icon from './Icon'
import { LoopMark } from './Brand'
export type DemoTab = 'notes' | 'cards' | 'progress'
export default function ProductDemo({ initialTab = 'notes' }: { initialTab?: DemoTab }) {
 const [tab, setTab] = useState<DemoTab>(initialTab)
 const [revealed, setRevealed] = useState(false)
 const [rating, setRating] = useState('')
 return <div className="product-window">
  <div className="window-chrome"><div className="window-dots"><i/><i/><i/></div><span>你的学习空间</span><span className="sample-label">交互示例</span></div>
  <div className="product-body">
   <aside className="product-sidebar"><div className="demo-user"><span className="mini-avatar">M</span><strong>我的知识空间</strong></div><span className="sidebar-caption">学习工具</span>
    {([{id:'notes',icon:'file',name:'知识笔记'},{id:'cards',icon:'cards',name:'记忆卡片'},{id:'progress',icon:'chart',name:'学习画像'}] as const).map(t=><button key={t.id} className={tab===t.id?'selected':''} onClick={()=>setTab(t.id)}><Icon name={t.icon} size={16}/>{t.name}{t.id==='cards'&&<em>3</em>}</button>)}
    <span className="sidebar-caption">我的资料</span><div className="demo-folder">⌄ &nbsp; 计算机科学</div><div className="demo-subfile">数据结构 · 栈与队列</div><div className="demo-folder">› &nbsp; 学习方法</div><div className="sidebar-brand"><LoopMark size={18}/> MemoLoop</div>
   </aside>
   <div className="product-content" aria-live="polite">
    <div className="demo-breadcrumb">计算机科学 <span>/</span> 数据结构 <span>/</span> {tab==='notes'?'知识笔记':tab==='cards'?'记忆卡片':'学习画像'} <Icon name="spark" size={16}/></div>
    {tab==='notes'?<><div className="demo-doc-title"><span className="doc-color"><Icon name="file" size={22}/></span><h3>栈与队列：理解两种数据结构</h3></div><div className="demo-meta"><span>数据结构.pdf · 第 12 页</span><span className="ml-badge is-ok">知识点已整理</span></div><h4>01 &nbsp; 栈 Stack</h4><p>一种受限的线性结构，只允许在同一端进行插入与删除。</p><div className="note-highlight"><span>核心特性</span>后进先出（LIFO）<span className="note-card-icon"><Icon name="cards" size={15}/></span></div><ul className="demo-bullets"><li>入栈 push：将新元素放到栈顶</li><li>出栈 pop：移除栈顶元素</li><li>常见应用：函数调用、撤销操作、括号匹配</li></ul><div className="stack-illustration"><div className="stack-visual"><span>C</span><span>B</span><span>A</span></div><div><span className="stack-arrow">↓ push &nbsp; ↑ pop</span><strong>最后进来的，最先出去。</strong><small>把抽象的概念，变成看得见的理解。</small></div></div><div className="demo-note-footer"><Icon name="spark" size={15}/> 从资料到理解，再到长期记忆 <button onClick={()=>setTab('cards')}>练习这张卡片 <Icon name="arrow" size={14}/></button></div></>:
    tab==='cards'?<div className="demo-review"><span className="eyebrow">主动回忆 · 示例卡片</span><h3>浏览器的“后退”功能，<br/>适合用哪种数据结构实现？</h3><div className="demo-answer">{revealed?<><strong>栈（Stack）</strong><p>最近访问的页面最先返回，符合后进先出（LIFO）的特点。</p></>:<p>先试着用自己的话回答，再查看解析。</p>}</div>{!revealed?<button className="ml-btn ml-btn-primary" onClick={()=>setRevealed(true)}>查看答案 <Icon name="chevron" size={16}/></button>:<><p className="rating-prompt">你对这个知识点有多熟悉？</p><div className="demo-ratings">{['还需练习','基本掌握','轻松记住'].map(r=><button className={rating===r?'active':''} key={r} onClick={()=>setRating(r)}>{r}</button>)}</div>{rating&&<p className="demo-feedback"><Icon name="check" size={16}/> 已选择“{rating}” · 示例体验不写入学习记录</p>}</>}<button className="reset-demo" onClick={()=>{setRevealed(false);setRating('')}}>重新练习</button></div>:
    <div className="demo-progress"><span className="eyebrow">每一小步，都看得见</span><h3>知识正在一点点沉淀。</h3><div className="demo-numbers"><div><strong>24<small>个</small></strong><span>示例知识点</span></div><div><strong>86<small>%</small></strong><span>示例记忆保有率</span></div></div><div className="week-bars" aria-label="示例学习记录：周一至周日"><span style={{height:'35%'}}/><span style={{height:'55%'}}/><span style={{height:'45%'}}/><span style={{height:'75%'}}/><span style={{height:'63%'}}/><span style={{height:'88%'}}/><span style={{height:'100%'}}/></div><div className="week-labels">{'一二三四五六日'.split('').map(d=><span key={d}>{d}</span>)}</div><p className="sample-note">以上为示例数据。实际学习画像根据你的复习记录生成。</p></div>}
   </div>
  </div>
 </div>
}
