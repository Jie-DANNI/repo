"""向量与混合检索服务（P3 核心）。

- embed_chunks: 文档切块批量向量化（幂等，只处理 embedding IS NULL 的块）
- hybrid_search: 向量余弦 + trigram 关键词，RRF(k=60) 融合
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import embed
from app.core.config import settings

RRF_K = 60


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def embed_chunks(db: AsyncSession, document_id: int) -> int:
    """给文档切块补写向量，返回本次写入数量。幂等。"""
    rows = (
        await db.execute(
            text("SELECT id, content FROM chunks WHERE document_id = :did AND embedding IS NULL ORDER BY id"),
            {"did": document_id},
        )
    ).all()
    if not rows:
        return 0
    vecs = await embed([r.content for r in rows])
    for (row, vec) in zip(rows, vecs):
        await db.execute(
            text("UPDATE chunks SET embedding = CAST(:v AS vector) WHERE id = :id"),
            {"v": _vec_literal(vec), "id": row.id},
        )
    await db.commit()
    return len(rows)


async def _vector_channel(db: AsyncSession, user_id: int, query_vec: list[float], top_k: int) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, content, heading_path, 1 - (embedding <=> CAST(:v AS vector)) AS score
                FROM chunks
                WHERE user_id = :uid AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:v AS vector)
                LIMIT :k
                """
            ),
            {"v": _vec_literal(query_vec), "uid": user_id, "k": top_k * 3},
        )
    ).all()
    return [
        {"id": r.id, "content": r.content, "heading_path": r.heading_path, "score": float(r.score)}
        for r in rows
    ]


async def _keyword_channel(db: AsyncSession, user_id: int, query: str, top_k: int) -> list[dict]:
    """pg_trgm 相似度通道：关键词命中的硬召回，弥补向量对术语/编号的弱项。"""
    rows = (
        await db.execute(
            text(
                """
                SELECT id, content, heading_path,
                       similarity(content, :q) AS score
                FROM chunks
                WHERE user_id = :uid AND (content %% :q)
                ORDER BY similarity(content, :q) DESC
                LIMIT :k
                """
            ),
            {"q": query, "uid": user_id, "k": top_k * 3},
        )
    ).all()
    return [
        {"id": r.id, "content": r.content, "heading_path": r.heading_path, "score": float(r.score)}
        for r in rows
    ]


def _rrf_fuse(channels: list[list[dict]], top_k: int) -> list[dict]:
    """Reciprocal Rank Fusion: score = Σ 1/(k + rank)。"""
    fused: dict[int, dict] = {}
    for channel in channels:
        for rank, item in enumerate(channel, start=1):
            rec = fused.setdefault(item["id"], {**item, "rrf": 0.0})
            rec["rrf"] += 1.0 / (RRF_K + rank)
    return sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)[:top_k]


async def hybrid_search(db: AsyncSession, user_id: int, query: str, top_k: int = 6) -> dict[str, Any]:
    """混合检索：返回向量/关键词/融合三组结果（融合结果给业务，三组给调试与技术文档实验）。"""
    qvec = (await embed([query]))[0]
    vec_hits = await _vector_channel(db, user_id, qvec, top_k)
    kw_hits = await _keyword_channel(db, user_id, query, top_k)
    fused = _rrf_fuse([vec_hits, kw_hits], top_k)
    return {"vector": vec_hits[:top_k], "keyword": kw_hits[:top_k], "fused": fused}


async def set_kp_embedding(db: AsyncSession, kp_id: int, content: str) -> None:
    """知识点卡片向量化（出题时检索相近考点用）。"""
    vec = (await embed([content]))[0]
    await db.execute(
        text("UPDATE knowledge_points SET embedding = CAST(:v AS vector) WHERE id = :id"),
        {"v": _vec_literal(vec), "id": kp_id},
    )
