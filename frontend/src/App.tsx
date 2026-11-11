import { useEffect, useLayoutEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Demo from './pages/Demo'
import Documents from './pages/Documents'
import Home from './pages/Home'
import Login from './pages/Login'
import Review from './pages/Review'
import Stats from './pages/Stats'
import { useAuth } from './store/auth'

/** 路由守卫：未登录跳登录页，并记住来源路径 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const user = useAuth((s) => s.user)
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  const restore = useAuth((s) => s.restore)
  const { pathname } = useLocation()
  useLayoutEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }) }, [pathname])

  // 应用启动时用本地 token 校验登录态（刷新不掉线）
  useEffect(() => {
    restore()
  }, [restore])

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/demo" element={<Demo />} />
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="workspace" element={<Home />} />
        <Route path="documents" element={<Documents />} />
        <Route path="review" element={<Review />} />
        <Route path="stats" element={<Stats />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
