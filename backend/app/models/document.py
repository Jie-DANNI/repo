"""文档与切块模型（对应 db/schema.sql 的 documents / chunks 表）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))  # pdf / md / txt
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer)
    # uploaded → parsing → chunked → extracted → failed
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    parse_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    content: Mapped[str] = mapped_column(Text)
    heading_path: Mapped[str | None] = mapped_column(Text)  # 如 "3 偏差与方差 > 3.2 分解"
    page_no: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # embedding 由 pgvector 处理，模型层不映射（向量列类型由扩展提供）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
