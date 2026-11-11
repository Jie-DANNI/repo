type IconName = 'arrow' | 'file' | 'cards' | 'spark' | 'chart' | 'loop' | 'check' | 'chat' | 'upload' | 'home' | 'menu' | 'close' | 'play' | 'chevron' | 'logout'
const paths: Record<IconName, string> = {
 arrow:'M5 12h14m-6-6 6 6-6 6', file:'M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5Zm0 0v5h5M8 12h8m-8 4h6',
 cards:'M8 5h11v15H8zM5 17H3V2h11v1',spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',chart:'M4 3v17h17M8 15v-4m5 4V6m5 9V9',loop:'M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5m-4 8a8 8 0 0 0 14 3l3-3m0 5v-5h-5',check:'m5 12 4 4L19 6',chat:'M21 11a8 8 0 0 1-8 8H8l-5 3V11a9 9 0 0 1 18 0ZM7 10h10m-10 4h6',upload:'M12 15V3m-4 4 4-4 4 4M4 15v6h16v-6',home:'m3 10 9-7 9 7M5 9v12h14V9m-10 12v-7h6v7',menu:'M4 6h16M4 12h16M4 18h16',close:'m6 6 12 12M6 18 18 6',play:'m8 4 12 8-12 8V4Z',chevron:'m6 9 6 6 6-6',logout:'M9 4H4v16h5m4-12 4 4-4 4m-5-4h13'
}
export default function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
 return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>
}
