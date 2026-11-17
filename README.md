# 忆循环 MemoLoop — AI 遗忘曲线学习管家

> 2026 第九届传智杯全国大学生数智创新与AI应用大赛 · AI WEB 网页开发挑战赛（研究生组）参赛作品

## 🎯 项目介绍

**忆循环 MemoLoop** 是一个基于「AI + 认知科学」的学习复习平台。上传学习资料（PDF / 课件）后，系统自动完成：**解析切块 → 知识点抽取建卡 → 向量入库 → FSRS 记忆模型调度复习**。

它的三个核心机制，让复习从"重复看"变成"递进地记住"：

1. **题型随记忆深度升级**：每张知识卡的题型不是固定的，而是随 FSRS 记忆状态递进——识别（判断）→ 选择 → 情景应用 → 费曼式讲解，记忆越深，考得越"活"
2. **错因驱动定向追问**：AI 评分时输出结构化错因标签（固定词表），下一轮由 Socratic Agent 针对错因定向追问，而不是泛泛重问
3. **工程化 RAG 混合检索**：向量检索（pgvector + bge-m3）与 BM25 关键词检索 RRF 融合，兼顾语义与术语命中

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│  前端 React 18 + TypeScript + Vite + Tailwind + Zustand  │
│  （SSE 打字机流式渲染 · 复习卡片流 · 追问抽屉 · 热力图） │
└──────────────────────┬──────────────────────────────────┘
                       │ /api（nginx 反代，SSE 关缓冲）
┌──────────────────────▼──────────────────────────────────┐
│  后端 FastAPI + SQLAlchemy(async) + SSE                  │
│                                                          │
│  三 Agent 协作：                                          │
│  ① Extractor  解析文档 → 抽取知识卡（JSON 严格校验+重试）│
│  ② Quizmaster 按复习轮次生成升级题型（recognition→       │
│     choice→scenario→feynman），SSE 流式输出              │
│  ③ Socratic   按错因标签定向追问                         │
│                                                          │
│  FSRS-4.5 记忆调度 · RAG 混合检索（向量+BM25，RRF 融合） │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  PostgreSQL 16 + pgvector（13 张表，vector(1024) HNSW）  │
└─────────────────────────────────────────────────────────┘
```

| 层 | 选型 | 选型理由 |
|---|---|---|
| 前端 | React 18 + Vite + TS + Tailwind + Zustand + ECharts | 生态主流；Zustand 轻量状态管理；ECharts 热力图 |
| 后端 | FastAPI + SQLAlchemy(async) + Pydantic | 原生异步 + SSE 流式；Pydantic 对 LLM 输出做强校验 |
| 数据库 | PostgreSQL 16 + pgvector | 业务数据与向量同库，免独立向量库运维；HNSW 索引保证检索性能 |
| 记忆模型 | fsrs-python（FSRS-4.5） | 较传统 SM-2 更优的记忆状态建模（stability/difficulty/retrievability） |
| 大模型 | OpenAI 协议兼容 LLM + bge-m3 Embedding(1024维) | 提示词与模型解耦，`prompt_versions` 表留痕可回溯 |
| 部署 | Docker Compose + Nginx | 前端多阶段构建，nginx 承担静态托管与 SSE 反代 |

## 🚀 在线演示（评审直通）

- **地址**：http://140.143.146.174
- **评审账号**：`demo@memoloop.cn` / `Demo@2026`
- 已预置《计算机网络·运输层核心讲义》及 19 张知识卡，登录即可完整体验「出题（流式）→ 作答 → 评分错因 → 定向追问 → FSRS 更新 → 热力图」全流程
- 服务由 cron 自愈脚本守护（每分钟健康检查，故障自动重启）

## 📦 安装运行指南

### 前置要求

- Docker + Docker Compose（生产部署，推荐）
- 或本地开发：Python 3.12 + Node 22

### 方式一：Docker 一键部署（生产）

```bash
# 1. 配置环境变量
cp .env.example .env    # 填入你的 LLM API Key（OpenAI 协议兼容）

# 2. 一键部署（自动构建、建库、预置演示数据）
bash deploy/init.sh
```

详细参数与故障排查见 `deploy/部署手册.md`。

### 方式二：本地开发

```bash
# 数据库
docker compose up -d postgres

# 后端（http://localhost:8000）
cd backend && pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload

# 前端（http://localhost:5173）
cd frontend && npm install && npm run dev
```

### 环境变量模板

所有密钥通过 `.env` 配置（见 `.env.example`），仓库不含任何真实密钥：

```ini
DATABASE_URL=postgresql+asyncpg://user:pwd@localhost:5433/memoloop
LLM_BASE_URL=...          # OpenAI 协议兼容的 LLM 服务地址
LLM_API_KEY=...           # 你的密钥
LLM_MODEL=...
EMBEDDING_BASE_URL=...
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=...
EMBEDDING_DIM=1024
JWT_SECRET=...
```

## 📂 目录结构

```
memoloop/
├── db/schema.sql              # 13 张表完整建库脚本（pgvector + HNSW）
├── backend/
│   ├── app/
│   │   ├── agents/            # extractor / quizmaster / scorer / socratic 四 Agent
│   │   ├── api/               # auth / documents / review / quiz / conversations / knowledge
│   │   ├── services/          # parser / vectors(RRF混合检索) / pipeline / review(FSRS)
│   │   └── core/              # config / security(JWT) / llm / constants(错因词表)
│   └── scripts/               # 演示数据种子脚本
├── frontend/src/
│   ├── pages/                 # Landing / Demo / 登录 / 工作台 / 复习 / 统计
│   ├── components/            # SocraticDrawer / 卡片流 / 布局组件
│   └── lib/                   # api / sse(流式客户端) / types
├── docs/                      # 方案与架构 / 数据库设计说明 / 操作演示手册
├── deploy/                    # 生产编排（compose.prod / nginx / init.sh / 自愈脚本 / 部署手册）
└── prompts/                   # 全流程阶段化开发提示词（开发方法留痕）
```

## 👥 团队信息

| 姓名 | 学校 | 分工 |
|------|------|------|
| （填写：队长姓名） | （填写：学校/学院/专业） | 产品设计、全栈开发、AI 方案与部署 |
| （指导教师） | （填写） | 指导教师 |

## ⭐ 创新点

1. **题型随记忆深度升级**——对标产品（Anki/Quizlet）题型固定重复，MemoLoop 将 FSRS 记忆状态与题型难度绑定，识别→选择→情景→费曼四级递进，复习即深度加工
2. **错因驱动定向追问**——评分 Agent 输出固定词表错因标签（如「概念混淆」「遗漏关键前提」），Socratic Agent 按标签生成针对性追问，而非模板化重问
3. **工程化 RAG 混合检索**——向量 + BM25 双路召回 RRF 融合，`prompt_versions` 表对提示词版本入库留痕，实验可复现

## 📄 更多文档

- 方案与架构：`docs/01_方案与架构.md`
- 数据库设计：`docs/02_数据库设计说明.md`
- 操作与演示手册：`docs/03_操作与演示手册.md`
- 技术文档（提交版 PDF 见提交材料）
