-- =====================================================================
-- 忆循环 MemoLoop · PostgreSQL 16 + pgvector 完整建库脚本
-- 执行顺序: 1) CREATE DATABASE memoloop;  2) 在该库中运行本脚本
-- 依赖扩展: CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------
-- 0. 用户与认证
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,                  -- bcrypt, 禁止明文
    nickname        VARCHAR(64)  NOT NULL,
    role            VARCHAR(16)  NOT NULL DEFAULT 'user',    -- user / demo (评审演示账号)
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 每个用户的长期学习画像（错因聚合，供出题 Agent 参考）
CREATE TABLE learning_profiles (
    user_id         BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    strengths       JSONB        NOT NULL DEFAULT '[]',     -- 已掌握主题标签
    weaknesses      JSONB        NOT NULL DEFAULT '[]',     -- 薄弱主题标签（定向追问依据）
    preferred_style VARCHAR(32)  NOT NULL DEFAULT 'balanced',
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 1. 内容层: 文档 → 切块 → 知识点
-- ---------------------------------------------------------------------
CREATE TABLE documents (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_type       VARCHAR(16)  NOT NULL,                   -- pdf / md / txt
    file_size       BIGINT      NOT NULL DEFAULT 0,
    page_count      INT,
    status          VARCHAR(16)  NOT NULL DEFAULT 'uploaded',
                    -- uploaded → parsing → chunked → extracted → failed
    parse_error     TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_user ON documents(user_id, status);

-- 文档切块（RAG 素材层）
CREATE TABLE chunks (
    id              BIGSERIAL PRIMARY KEY,
    document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content         TEXT    NOT NULL,
    heading_path    TEXT,                                   -- 所属标题层级路径, 如 "3.2>偏差与方差"
    page_no         INT,
    token_count     INT     NOT NULL DEFAULT 0,
    embedding       vector(1536),                            -- 与 Embedding 模型维度一致
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 向量检索索引（生产用 hnsw，数据量小可用 ivfflat）
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_doc  ON chunks(document_id);
-- BM25 由外部实现或用 tsvector 辅助；这里建轻量全文索引支撑关键词通道
CREATE INDEX idx_chunks_trgm ON chunks USING gin (content gin_trgm_ops);

-- 知识点卡片（Extractor Agent 产出）
CREATE TABLE knowledge_points (
    id              BIGSERIAL PRIMARY KEY,
    document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    content         TEXT        NOT NULL,                   -- 卡片正面内容（定义/公式/结论）
    summary        TEXT,                                    -- AI 生成的一句话摘要
    keywords        JSONB       NOT NULL DEFAULT '[]',
    difficulty      SMALLINT    NOT NULL DEFAULT 3,          -- 1-5, 出题难度基准
    importance      SMALLINT    NOT NULL DEFAULT 3,          -- 1-5, 考纲权重
    embedding       vector(1536),                            -- 知识点级向量（题目生成时检索相近考点）
    status          VARCHAR(16) NOT NULL DEFAULT 'active',  -- active / suspended / archived
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, title)
);
CREATE INDEX idx_kp_user ON knowledge_points(user_id, status);
CREATE INDEX idx_kp_embedding ON knowledge_points USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------
-- 2. 调度层: FSRS 记忆模型
-- 记忆状态存于 review_records; review_logs 为全量日志（统计页/热力图数据源）
-- ---------------------------------------------------------------------
CREATE TABLE review_records (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id  BIGINT NOT NULL UNIQUE REFERENCES knowledge_points(id) ON DELETE CASCADE,
    -- FSRS-4.5 状态
    stability           REAL   NOT NULL DEFAULT 0,           -- 记忆稳定性(天)
    difficulty          REAL   NOT NULL DEFAULT 0,           -- 难度(0-10)
    retrievability      REAL   NOT NULL DEFAULT 1,          -- 当前可提取性(0-1)
    reps                SMALLINT NOT NULL DEFAULT 0,       -- 已复习次数 = review_round 基础
    lapses              SMALLINT NOT NULL DEFAULT 0,       -- 遗忘次数
    state               VARCHAR(16) NOT NULL DEFAULT 'new', -- new/learning/review/relearning
    due_at              TIMESTAMPTZ NOT NULL DEFAULT now(), -- 下次到期时间(调度核心字段)
    last_reviewed_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_review_user_due ON review_records(user_id, due_at)
    WHERE state <> 'new';

-- 每次复习的完整日志（谁、哪题、什么时候、评级是什么、下次何时）
CREATE TABLE review_logs (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id  BIGINT NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    review_record_id    BIGINT NOT NULL REFERENCES review_records(id) ON DELETE CASCADE,
    review_round        SMALLINT NOT NULL,                   -- 第几轮复习（决定题型等级）
    scheduled_at        TIMESTAMPTZ NOT NULL,
    actual_at           TIMESTAMPTZ NOT NULL,
    rating              SMALLINT NOT NULL,                   -- FSRS: 1=again 2=hard 3=good 4=easy
    quiz_item_id        BIGINT,                              -- 本轮使用的题目
    new_stability       REAL,
    new_due_at          TIMESTAMPTZ
);
CREATE INDEX idx_review_logs_user_time ON review_logs(user_id, actual_at DESC);

-- ---------------------------------------------------------------------
-- 3. 作答层: 出题 → 作答 → 评分 → 追问
-- ---------------------------------------------------------------------
CREATE TABLE quiz_items (
    id                  BIGSERIAL PRIMARY KEY,
    knowledge_point_id  BIGINT NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    review_round        SMALLINT NOT NULL,                   -- 生成时的复习轮次
    quiz_type           VARCHAR(24) NOT NULL,
        -- round1: recognition(判断/填空)   round2: choice(选择/简答)
        -- round3: scenario(情景应用)       round4+: feynman(费曼式讲解)
    question            TEXT        NOT NULL,
    options             JSONB,                              -- 客观题选项
    answer              TEXT,                               -- 参考答案/量规要点
    rubric              JSONB       NOT NULL DEFAULT '[]',  -- 评分要点列表 [{point, weight}]
    explanation         TEXT,                               -- 考点解析
    generation_meta     JSONB       NOT NULL DEFAULT '{}',  -- model/prompt_version/latency_ms/tokens
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_quiz_kp_round ON quiz_items(knowledge_point_id, review_round);

CREATE TABLE quiz_responses (
    id                  BIGSERIAL PRIMARY KEY,
    quiz_item_id        BIGINT NOT NULL REFERENCES quiz_items(id) ON DELETE CASCADE,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answer_text         TEXT,                               -- 用户作答（客观题存选项id）
    selected_option     JSONB,
    score               REAL,                               -- 0-1, rubric 加权
    error_tags          JSONB        NOT NULL DEFAULT '[]',  -- ★错因标签: 定向追问的依据
    ai_feedback         TEXT,                               -- 逐条量规反馈
    answered_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_resp_user_kp ON quiz_responses(user_id, quiz_item_id);

-- 苏格拉底追问会话（一题一次答错/不完美 → 一条会话）
CREATE TABLE conversations (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id  BIGINT NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    quiz_item_id        BIGINT REFERENCES quiz_items(id) ON DELETE SET NULL,
    trigger_tags        JSONB       NOT NULL DEFAULT '[]',  -- 触发本次追问的历史错因标签
    status              VARCHAR(16) NOT NULL DEFAULT 'open',-- open / closed
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id                  BIGSERIAL PRIMARY KEY,
    conversation_id     BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                VARCHAR(16) NOT NULL,               -- user / assistant
    content             TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_conv ON messages(conversation_id, created_at);

-- ---------------------------------------------------------------------
-- 4. 实证层: prompt 版本管理（技术文档"优化策略"数据源，评委最吃这套）
-- ---------------------------------------------------------------------
CREATE TABLE prompt_versions (
    id                  BIGSERIAL PRIMARY KEY,
    scene               VARCHAR(32) NOT NULL,               -- extract / quiz / score / socratic
    version             INT         NOT NULL,
    template            TEXT        NOT NULL,
    notes               TEXT,                               -- 改动动机与效果（例: v3 加入错因标签后评分一致性+xx%）
    metrics             JSONB       NOT NULL DEFAULT '{}',  -- 抽样评测结果
    active              BOOLEAN     NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scene, version)
);

-- 每日复习统计（热力图直接查，避免大表聚合）
CREATE TABLE daily_stats (
    user_id             BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stat_date           DATE    NOT NULL,
    reviews_done        INT     NOT NULL DEFAULT 0,
    avg_score           REAL,
    cards_touched       INT     NOT NULL DEFAULT 0,
    minutes             REAL,
    PRIMARY KEY (user_id, stat_date)
);
