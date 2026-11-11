# MemoLoop 页面升级说明

本版在原 React + Vite + TypeScript 项目上改造，借鉴 RemNote 中文官网的浅色渐变、居中主标题、产品界面展示、左右交错功能区及折叠 FAQ。品牌、文案、图标、插图、组件和交互均为 MemoLoop 自有实现，未复制 RemNote 的商标、截图和用户评价。

## 页面与路由

- `/`：新增公开产品首页。包含可操作的笔记/卡片/画像示例、功能切换、资料上传入口、三段功能说明、学习流程、FAQ。
- `/demo`：免登录交互示例。内置内容有明确示例标识，不写入真实学习记录，不调用大模型。
- `/login`：全新登录/注册页面，保留原认证接口；`?mode=register` 直接显示注册。
- `/workspace`：原工作台移动到此路由，采用侧栏导航、学习主卡、概览指标与快捷入口。
- `/documents`、`/review`、`/stats`：原路径和业务接口保持，统一应用外壳与设计样式。
- 未登录访问受保护页面仍会进入登录页，登录后返回原目标页面。

## 运行

沿用原项目后端和数据库。前端目录执行：

```bash
npm ci
npm run dev
```

本地 Vite 继续将 `/api` 转发到 `http://localhost:8000`。后端依赖、数据库、模型 API 配置和种子数据初始化方式保持原项目不变。

```bash
npm run build
```

生成正常生产版本；真实登录、上传、AI 出题和追问需要可用的后端以及同源 `/api` 反向代理。部署时须配置 SPA fallback，将非 API 的页面导航回退至 `index.html`。

若只发布无需后端的界面演示：

```bash
npx tsc -b
npx vite build --mode showcase
```

此模式读取 `.env.showcase`，登录页明确显示界面预览提示，阻止实际认证请求；交互示例仍可使用。不要用此模式替代需要真实登录的正式部署。

## 改动位置

- `src/design.css`：新版视觉系统、首页、登录、工作台及响应式规则。
- `src/theme.css`：原基础组件令牌仍保留；新样式在其后加载。
- `src/components/Brand.tsx`、`Icon.tsx`：原创循环标志和 SVG 线性图标。
- `src/components/ProductDemo.tsx`：可操作的产品示例。
- `src/pages/Landing.tsx`、`Demo.tsx`：新增首页和体验页。
- `src/components/Layout.tsx`、`src/pages/Home.tsx`、`Login.tsx`：应用导航、工作台和登录改版。
- `src/pages/Documents.tsx`：上传区域键盘操作、格式/大小前置检查、上传忙碌状态处理。
- `src/pages/Review.tsx`：修复空队列或请求失败时停留在加载态的问题。
- `src/pages/Stats.tsx`：视觉标题及文案调整。
- `src/App.tsx`：路由调整、页面切换回到顶部。

## 验证

已通过 TypeScript 和 Vite 构建；浏览器检查桌面首页、工作台，以及 390px 宽容器中的手机首页/体验/登录排版；验证移动菜单、FAQ、笔记/卡片/画像切换、翻卡、自评和工作台导航。对空复习队列、失败请求进行了隔离测试。工作台视觉检查使用临时测试数据，未连接真实后端、数据库或模型 API；后端全链路需在原部署环境回归。

所有演示值仅用于展示交互，不代表真实用户规模、成绩或学习效果。
