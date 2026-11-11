import { Link } from 'react-router-dom'
import Brand from '../components/Brand'
import Icon from '../components/Icon'
import ProductDemo from '../components/ProductDemo'
export default function Demo(){return <div className="demo-page"><header><Brand/><Link to="/">返回首页 ↗</Link></header><div className="demo-page-heading"><span className="eyebrow">MEMOLOOP · 交互示例</span><h1>先体验，再开始学习。</h1><p>点击左侧「知识笔记」「记忆卡片」「学习画像」，探索完整流程。<br/>内置示例无需登录，不上传文件，也不写入真实学习记录。</p></div><div className="demo-page-window"><ProductDemo/></div><div className="demo-page-bottom"><span>准备好把自己的资料变成知识了吗？</span><Link className="ml-btn ml-btn-primary" to="/login?mode=register">创建我的学习空间 <Icon name="arrow" size={16}/></Link></div></div>}
