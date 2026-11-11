"""数据库连接与会话管理。"""
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SCHEMA_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "db" / "schema.sql",  # 本地: memoloop/db/schema.sql
    Path("/db/schema.sql"),                                     # 容器: ./db 挂载到 /db
]


def _schema_path() -> Path:
    for p in SCHEMA_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(f"未找到 schema.sql，尝试过: {SCHEMA_CANDIDATES}")


async def init_schema_if_needed() -> None:
    """首次启动时若表不存在则执行 schema.sql（docker 初始化已跑过则自动跳过）。"""
    async with engine.begin() as conn:
        exists = await conn.exec_driver_sql(
            "SELECT to_regclass('public.users') IS NOT NULL"
        )
        if exists.scalar():
            return
        sql = _schema_path().read_text(encoding="utf-8")
        await conn.exec_driver_sql(sql)


async def get_db():
    """FastAPI 依赖：提供一个会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
