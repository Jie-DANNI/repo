import { Link } from 'react-router-dom'

export function LoopMark({ size = 32 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 36 36" fill="none" aria-hidden="true"><rect width="36" height="36" rx="11" fill="currentColor"/><path d="M18 13.3c-4-6.5-12.2-2.5-10 3.8 1.7 4.9 6.8 4.3 10 .9 3.2-3.4 8.3-4 10 .9 2.2 6.3-6 10.3-10 3.8" stroke="white" strokeWidth="3.1" strokeLinecap="round"/><path d="m16 9 2 4.3-4.7.6m6.7 13.3-2-4.3 4.7-.6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
}
export default function Brand({ to = '/' }: { to?: string }) {
  return <Link to={to} className="ml-brand" aria-label="MemoLoop 忆循环首页"><LoopMark/><span>MemoLoop<span className="brand-cn">忆循环</span></span></Link>
}
