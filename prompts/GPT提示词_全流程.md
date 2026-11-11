# GPT 提示词 · 忆循环 MemoLoop 全流程（11 个阶段）

> **用法**：每条提示词独立成段，按顺序逐条发给 GPT。发送时把文末「全局上下文」一并粘贴（或先发全局上下文再发阶段提示词）。
> **纪律**：一次只发一条，拿到代码跑通、commit 之后再发下一条。GPT 给的代码要人工过一遍再提交——评委看 Git 历史也看代码质量。
> **验收**：每条提示词末尾都有「验收标准」，不达标就追问 GPT 修到达标为止，再进入下一阶段。

---

## P0 · 工程脚手架（Day 1）

```
你是资深全栈工程师。为我搭建项目「忆循环 MemoLoop」的 Monorepo 脚手架，要求如下。

技术栈：
- 前端 frontend/：React 18 + Vite + TypeScript + TailwindCSS + Zustand + React Router，含 axios 封装（统一 baseURL=/api、401 拦截跳登录）
- 后端 backend/：Python FastAPI + SQLAlchemy(async) + asyncpg + Pydantic v2，目录含 app/{api,models,schemas,services,agents,core}，其中 core/config.py 用 pydantic-settings 读环境变量
- 根目录：docker-compose.yml 定义 postgres:16 + pgvector/pgvector:pg16 镜像服务（healthcheck）、backend、frontend；.env.example 列出 DATABASE_URL / LLM_API_KEY / LLM_BASE_URL / EMBEDDING_MODEL / JWT_SECRET；.gitignore 覆盖 .env/node_modules/__pycache__/dist
- db/schema.sql 已存在，提供 backend 的初始化脚本：启动时自动 CREATE EXT IF NOT EXISTS vector 并执行该 schema

验收标准：
1. docker compose up 后：postgres 健康、backend 在 :8000 返回 {"app":"memoloop"}、前端在 :5173 显示登录页占位
2. 前后端 CORS 已配好，curl http://localhost:8000/health 正常
3. 给出完整的启动命令序列（含首次安装依赖）

请输出：完整目录树 + 所有文件代码 + 启动步骤。不要省略任何文件。
```

---

## P1 · 用户认证（Day 1 晚）

```
在上述 FastAPI 项目中实现用户认证模块。

需求：
1. POST /api/auth/register（email/nickname/password，bcrypt 哈希，校验邮箱格式与密码强度）
2. POST /api/auth/login → 返回 JWT access_token（有效期 7 天，JWT_SECRET 来自环境变量）
3. 依赖注入 get_current_user，所有后续业务路由将使用它；401 返回统一错误结构 {"detail": "..."}
4. 附带一个 seed 脚本 backend/scripts/seed_demo.py：创建 role='demo' 的演示账号 demo@memoloop.cn / Demo@2026
5. 前端对应页面：登录/注册页 + axios 拦截自动带 Bearer token + 401 清 token 跳登录

验收：用 curl 完成 注册→登录→带 token 访问 /api/auth/me 全流程；前端能真实注册登录并跳转到空白首页。
```

---

## P2 · 文档上传与解析切块（Day 2）

```
实现文档上传解析流水线。

需求：
1. POST /api/documents 上传 PDF/MD/TXT（限 50MB），存到 backend/storage/{user_id}/，documents 表记录 status='uploaded'
2. 后台任务（FastAPI BackgroundTasks）：用 pymupdf 提取 PDF 文本，按标题层级（字体大小/编号样式识别，Markdown 按 # 层级）递归切块：
   - 每块带 heading_path（如 "3 偏差与方差 > 3.2 分解"）
   - 目标块长 300-600 token，超长按段落再分，记录 page_no 与 token_count
   - status 依次更新 parsing → chunked，失败则 failed 并记 parse_error
3. GET /api/documents 列出当前用户文档及状态；GET /api/documents/{id}/chunks 分页预览切块结果

验收：上传一份 30 页课件 PDF，60 秒内 status=chunked，chunks 表有合理切块且 heading_path 不为空；上传损坏文件返回友好错误而非 500。
```

---

## P3 · Embedding 与混合检索（Day 2）

```
实现 RAG 检索通道。

需求：
1. core/llm.py：封装 OpenAI 协议兼容客户端（base_url、api_key 全部来自环境变量），提供 embed(texts: list[str]) → list[list[float]]，批量≤64 条，失败重试 2 次、指数退避
2. chunked 后自动为 chunks 写入 embedding（1536 维）
3. 实现 hybrid_search(user_id, query, top_k)：向量余弦检索（pgvector）+ 关键词检索（gin_trgm 相似度），用 RRF（k=60）融合排序，返回 chunk 列表
4. 提供调试端点 GET /api/debug/search?q=...（仅 role=demo 可用）直接返回融合前后两列结果，便于我在技术文档里做检索质量对比

验收：同一 query 下，能看到向量通道、关键词通道与 RRF 融合后三个排序结果；embedding 写入有批量优化而不是逐条网络请求。
```

---

## P4 · Extractor 知识点抽取 Agent（Day 2 完）

```
实现 Extractor Agent（知识点抽取）。

需求：
1. 对 status=chunked 的文档：按 heading_path 分组，每次把一组相关 chunks + 检索到的邻近块交给 LLM，prompt 要求：
   - 抽取可独立复习的知识点，每个输出 {title, content(卡片正面:定义/公式/结论), summary, keywords[], difficulty(1-5), importance(1-5)}
   - 明确指示：跳过目录、页眉页脚、纯过渡句；同一概念只出一个卡片
2. 输出强制 JSON（response_format=json_object + Pydantic 校验），解析失败重试≤2次
3. 逐条写入 knowledge_points（命中 document_id+title 唯一冲突则更新），同步写 embedding 与 review_records(state='new', due_at=now)
4. 完成后 documents.status='extracted'；提供 GET /api/knowledge-points?document_id= 分页查看
5. 把本次使用的 prompt 模板写入 prompt_versions(scene='extract', version=1, notes='初版')

验收：30 页课件抽取 40-80 个结构合理的知识点，无重复标题；状态机完整走完；重复执行不产生重复卡片。
```

---

## P5 · FSRS 复习调度（Day 3）

```
实现复习调度模块。

需求：
1. 使用 fsrs-python 库（FSRS-4.5）。为每张卡片维护 review_records 的 stability/difficulty/retrievability/state/reps/lapses/due_at
2. GET /api/review/today：取当前用户 due_at<=now 的卡片，按 due_at 升序限 20 张（不足时从 state='new' 的卡片补齐），返回卡片元数据（不含题目）
3. POST /api/review/{kp_id}/grade：body 含 rating(1-4)，用 FSRS 更新记忆状态，写 review_logs（review_round=reps, rating, 新旧 stability/due_at 快照），同步更新 daily_stats（upsert）
4. review_round 映射规则写死在 service 层：round1→recognition, 2→choice, 3→scenario, ≥4→feynman；同时为 role='demo' 提供 POST /api/review/{kp_id}/advance-round 手动推进轮次（用于演示视频，普通用户 403）

验收：新卡 first rating=3 后 due_at 推迟到几分钟到数小时内；rating=1 后 stability 下降、进入 relearning；today 列表按调度顺序返回；连续作答后 daily_stats 正确累计。
```

---

## P6 · Quizmaster 出题 Agent（Day 3 完，全项目最重）

```
实现 Quizmaster Agent（升级题型生成）。

需求：
1. POST /api/review/{kp_id}/quiz：按当前 review_round 的 quiz_type 生成题目，**SSE 流式返回**
2. 出题输入：knowledge_points 全量字段 + 该卡片历史 quiz_responses.error_tags 聚合 + learning_profiles.weaknesses + 用户前几轮题目列表（避免重复问法）
3. 各题型 prompt 要求：
   - recognition(r1)：判断题（含 50% 反例干扰）或关键词填空，options/answer 客观可比
   - choice(r2)：四选一，干扰项必须来自学员常见误解（prompt 中列出该知识点 Top 误解），附 rubric
   - scenario(r3)：结合 weaknesses 的真实场景应用题，rubric 为 3-4 个 {point, weight} 要点，weight 合计=1
   - feynman(r4+)："向零基础者讲解"，prompt 要求 AI 之后将扮演追问的小白，rubric 侧重完整性与类比质量
4. 生成时同步：检索 2-3 个相近 knowledge_points 的 embedding 相邻块作为上下文（防脱离原文）；输出写 quiz_items（含 generation_meta：model/prompt_version/latency_ms/prompt+completion tokens）
5. 流式协议：SSE 事件依次为 {"type":"meta",...} → 多条 {"type":"chunk","text":...} → {"type":"done","quiz_item_id":n}；JSON 结构部分（options/rubric）整体在 done 前下发
6. prompt 写入 prompt_versions(scene='quiz', version=1)

验收：同一卡片连点 4 次生成，4 种题型随 round 递进且问法不重复；弱项考点在 r3 题干中明显体现；curl -N 能看到流式分片到达；一次失败重试后仍失败时降级为返回静态填空题（保证复习不中断）。
```

---

## P7 · 评分与错因标签（Day 4）

```
实现作答评分模块。

需求：
1. POST /api/quiz/{quiz_item_id}/answer：body 含 answer_text（主观）或 selected_option（客观）
2. 客观题：直接比对，score=0/1
3. 主观题：把 quiz_item.rubric + 参考答案 + 用户作答交给 LLM，输出严格 JSON：{score:0-1, per_point:[{point, hit:bool, comment}], error_tags:[], feedback:str}
   - error_tags 从固定词表中选（词表存 core/constants.py：如 概念混淆/边界条件缺失/公式误用/因果倒置/表述不严谨/举例不当/遗漏关键前提），prompt 明确"只从词表选，禁止自造"
4. 写 quiz_responses(score, error_tags, ai_feedback)，同时按结果换算 FSRS rating（score≥0.9→4, ≥0.7→3, ≥0.4→2, 其余→1）调用 P5 的 grade 端点逻辑完成调度闭环
5. score<0.8 或 error_tags 非空 → 自动创建 conversations(trigger_tags=error_tags) 供 P8 使用
6. prompt 写入 prompt_versions(scene='score', version=1)

验收：故意答错一半要点，error_tags 命中词表且 per_point 逐条对应 rubric；同一答案评分两次偏差 ≤0.1；评分接口返回前端可直接渲染的结构。
```

---

## P8 · Socratic 定向追问（Day 4 完）

```
实现 Socratic Agent（错因定向追问会话）。

需求：
1. POST /api/conversations/{id}/messages：SSE 流式多轮对话
2. 系统角色设定：温和的苏格拉底式导师。**只围绕 trigger_tags 与本次用户回答中新暴露的错误追问**，一次只问一个问题，不直接给答案，用户答对后给确认并推进到下一个错因；全部错因补完或达到 5 轮上限时总结收束并置 conversations.status='closed'
3. 上下文构造：conversation 历史 + knowledge_points.content + 该用户历史 error_tags（同一标签第 3 次出现时换新问法）
4. 会话结束：把本轮 error_tags 聚合写 learning_profiles.weaknesses（出现频次+1，掌握则减）
5. prompt 写入 prompt_versions(scene='socratic', version=1)

验收：完整走一遍"答错→追问3轮→承认理解→AI收束"的会话；追问内容紧扣错因不跑题；weaknesses 数组随会话更新；关闭后再次触发同一知识点复习时，新题干可看出针对弱项。
```

---

## P9 · 前端全量页面（Day 5）

```
实现 React 前端全部页面。设计语言：清爽学术风（浅色为主，深蓝 #2563EB 强调色，卡片圆角阴影），移动端可用。

页面清单：
1. /login /register：居中卡片表单
2. /docs：上传区（拖拽+进度条）+ 文档列表（状态徽章：解析中/已建卡/失败），失败可看错误
3. /library：知识点卡片网格（标题/难度/到期时间/弱点标记），支持暂停(patched→suspended)
4. /review（核心页）：单卡片模式——顶部进度（今日 12/20），中部题目流式打字机渲染（fetch+ReadableStream 解析 SSE），答题区随题型切换（判断/选择按钮组 或 文本框），提交后展示逐条量规反馈+错因标签徽章，底部评分按钮（重来/困难/良好/简单）；score<0.8 时弹出追问对话抽屉（多轮气泡，流式）
5. /stats：ECharts 三图——复习热力图(日历)、记忆保有率曲线(retrievability 聚合)、错因 Top5 条形图
6. /profile：学习画像 strengths/weaknesses 可视化

通用：Zustand 全局 auth store；所有 AI 流式输出统一 hook useSSE；加载/错误态统一组件；页面路由守卫。

验收：与后端全部接口联调通过；复习全流程（出题流式→作答→反馈→追问抽屉→FSRS更新→热力图出现今日记录）一次无报错跑完；1080p 下布局无溢出。
```

---

## P10 · 部署上线（Day 6，加分行）

```
给出生产部署方案并实施。

要求：
1. docker-compose.prod.yml：frontend 多阶段构建（npm build → nginx 服务静态文件），backend 用 uvicorn workers=2，postgres 数据卷持久化
2. nginx.conf：/ 反代前端静态资源，/api 反代 backend:8000，SSE 路由（/api/review、/api/conversations、/api/quiz）单独配置 proxy_buffering off + proxy_read_timeout 300s
3. 提供首次初始化一键脚本 init.sh：建库、跑 schema.sql、seed 演示账号、导入一份预置课件并完成建卡（评委打开即有内容）
4. 我会部署到国内云服务器，请给出：安全组建议（只开 80/443）、HTTPS 用 certbot 一键配置命令、以及评审期间的可用性自检脚本（cron 每分钟 curl /health，失败时 docker compose restart backend）

验收：公网域名 https://xxx 可注册可登录可完整复习；SSE 在生产环境流式正常（这是最容易翻车点，请重点验证）；演示账号有预置数据。
```

---

## P11 · 技术文档与提交材料（Day 7）

```
帮我撰写传智杯技术文档（PDF，≤30页），项目「忆循环 MemoLoop」。

结构（严格按赛项要求）：
1. 项目概述与需求分析：痛点（固定题型重复复习的低效）→ 方案 → 目标用户
2. 系统架构设计：附架构图（Mermaid 绘制后转图）+ 技术选型理由表（每项写"为什么选它、对比了什么"）
3. AI 技术方案（重点章节）：三 Agent 职责与工作流图；RAG 混合检索设计（RRF 融合公式）；FSRS-4.5 记忆模型原理与题型升级机制；错因标签词表设计
4. 核心功能实现：每功能配关键代码片段（含中文注释）+ 难点解决方案（SSE 生产环境踩坑、LLM JSON 校验重试、批量 embedding）
5. 测试与部署：接口测试结果表、切块策略检索质量对比实验表、prompt 版本迭代表（引用 prompt_versions 表数据，写明每版改动动机与效果）
6. 创新点总结：①题型随记忆深度升级 ②错因驱动定向追问 ③工程化混合检索，每条都写"对标产品为什么没有做到"
7. 总结与展望

要求：用词专业但克制，不吹嘘；所有实验数据用占位表格框架给我，标注需要我实际跑出来后填入的位置。
```

---

## ★ 全局上下文（每次发提示词前先粘贴这段）

```
【全局上下文】
项目：忆循环 MemoLoop —— AI遗忘曲线学习管家，参加2026传智杯AI WEB网页开发挑战赛（研究生组）。
核心机制：上传PDF→切块入库(pgvector)→Extractor Agent抽取知识点→FSRS-4.5调度复习→Quizmaster Agent按复习轮次生成升级题型(识别→选择→情景→费曼)→rubric评分并输出错因标签(error_tags固定词表)→Socratic Agent按错因定向追问。
技术栈：React18+Vite+TS+Tailwind+Zustand / FastAPI+SQLAlchemy async / PostgreSQL16+pgvector(1536维) / fsrs-python / OpenAI协议兼容LLM。
数据库表：users, learning_profiles, documents, chunks, knowledge_points, review_records, review_logs, quiz_items, quiz_responses, conversations, messages, prompt_versions, daily_stats（schema 已存在于 db/schema.sql，业务代码必须与其字段完全一致）。
代码风格：中文注释，每个模块文件≤300行，API 统一 /api 前缀，密钥一律环境变量，错误统一 {"detail":...}。
当前工作目录为 Monorepo：frontend/ + backend/ + db/。
你给出的所有代码都要与上述表结构严格对齐，禁止臆造字段名。
```

---

## 使用心法（给你的，不用发给 GPT）

1. **P6 出题 Agent 是全项目灵魂**——它不达标，创新点①就立不住，时间不够时优先保它。
2. GPT 给的代码跑不通时，把**完整报错栈 + 相关文件代码**贴回去让它修，别自己硬扛，但也别让它大改已跑通的模块。
3. 每完成一个阶段：`git add -A && git commit -m "feat(模块): 描述"`，别攒一天一次性提交。
4. 技术文档里的**对比实验**（切块策略、prompt 版本表）只有你真实跑过才能写出数字——P3 和 P4 的调试端点就是为此准备的，留好数据。
