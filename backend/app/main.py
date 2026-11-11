"""忆循环 MemoLoop · FastAPI 入口。

P0 阶段职责：拉起服务、连通数据库、暴露健康检查，供前端联调探测。
后续阶段将在此注册 auth / documents / knowledge / review / quiz / conversations 路由。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db import engine, init_schema_if_needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保 pgvector 扩展与表结构就位（幂等）
    await init_schema_if_needed()
    yield
    await engine.dispose()


app = FastAPI(
    title="忆循环 MemoLoop API",
    description="AI 遗忘曲线学习管家 · 2026 传智杯 AI WEB 网页开发挑战赛",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"app": "memoloop", "version": app.version}


@app.get("/health")
@app.get("/api/health")
async def health():
    """健康检查：数据库连通 + 版本信息（部署后自检脚本就调这个）。"""
    db_ok = True
    db_version = ""
    try:
        async with engine.connect() as conn:
            db_version = (await conn.execute(text("SELECT version()"))).scalar() or ""
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "db_version": db_version[:60]}
