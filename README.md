# 忆循环 MemoLoop — AI 遗忘曲线学习管家

2026 第九届传智杯 · AI WEB 网页开发挑战赛（研究生组）参赛作品。

## 一句话定位

上传学习资料（PDF / 课件），AI 自动解析为知识点卡片，基于 **FSRS 记忆模型** 调度复习时机，且**每一轮复习的题型会随记忆状态升级**（识别 → 选择 → 情景追问 → 费曼式讲解），AI 会根据你上次答错的地方**定向追问**，让复习从"重复看"变成"递进地记住"。

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | React 18 + Vite + TypeScript + TailwindCSS + Zustand + ECharts | 主流、评审友好、动画表现力强 |
| 后端 | Python FastAPI + SQLAlchemy(async) + Pydantic | 异步、SSE 流式输出天然支持、AI 生态最全 |
| 数据库 | PostgreSQL 16 + pgvector | 关系数据与向量检索同一库，运维成本低 |
| 记忆模型 | fsrs-python（FSRS-4.5） | 比传统 SM-2 先进，研究生组技术深度加分点 |
| AI | 兼容 OpenAI 协议的大模型 API + Embedding 模型，RAG 混合检索（向量 + BM25） | 官方要求的 LLM + RAG 双命中 |
| 部署 | Docker Compose + Nginx | 在线演示加分项 |

## 目录结构

```
memoloop/
├── README.md
├── docs/
│   ├── 01_方案与架构.md      # 完整方案、创新点、7天排期
│   └── 02_数据库设计说明.md   # 表设计与业务流程对照
├── db/
│   └── schema.sql            # PostgreSQL + pgvector 完整建库脚本
├── prompts/
│   └── GPT提示词_全流程.md    # 10个阶段化提示词，直接复制使用
├── backend/                 # FastAPI 服务（骨架已规划，见 prompts/P0）
└── frontend/                # React 应用（骨架由 prompts/P0 生成）
```

## 关键文件

- 方案文档：`docs/01_方案与架构.md`
- 建库脚本：`db/schema.sql`
- GPT 提示词：`prompts/GPT提示词_全流程.md`（**你日常主要用的就是这个**）

## 冲刺纪律（务必遵守）

1. 从今天起每天真实 Git 提交，写有意义的 commit message；
2. API Key 一律走 `.env`，仓库里不出现任何密钥；
3. 11月16日前必须部署上线并注册评审测试账号；
4. 技术文档中的 prompt 版本表（`prompt_versions`）从第一天就开始记录。
