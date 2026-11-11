"""知识点与调度层 ORM（knowledge_points / review_records / review_logs）。

注意：两表的 embedding 向量列不在此映射，向量的读写统一走 raw SQL（见 services/vectors.py）。
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)  # 1-5
    importance: Mapped[int] = mapped_column(SmallInteger, default=3)  # 1-5
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReviewRecord(Base):
    """FSRS 记忆状态。retrievability 由调度时计算写入（非持久字段，缓存性质）。"""
    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    knowledge_point_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    stability: Mapped[float] = mapped_column(default=0.0)
    difficulty: Mapped[float] = mapped_column(default=0.0)
    retrievability: Mapped[float] = mapped_column(default=1.0)
    reps: Mapped[int] = mapped_column(SmallInteger, default=0)
    lapses: Mapped[int] = mapped_column(SmallInteger, default=0)
    state: Mapped[str] = mapped_column(String(16), default="new")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    knowledge_point_id: Mapped[int] = mapped_column(BigInteger)
    review_record_id: Mapped[int] = mapped_column(BigInteger)
    review_round: Mapped[int] = mapped_column(SmallInteger)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actual_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rating: Mapped[int] = mapped_column(SmallInteger)  # 1=again 2=hard 3=good 4=easy
    quiz_item_id: Mapped[int | None] = mapped_column(BigInteger)
    new_stability: Mapped[float | None]
    new_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
