"""知识库路由：知识点列表 / 混合检索调试端点（技术文档实验数据源）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_demo_user
from app.db import get_db
from app.models.user import User
from app.services.vectors import hybrid_search

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge-points")
async def list_knowledge_points(
    document_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识点卡片分页（含 FSRS 状态与弱点标记）。"""
    where = "kp.user_id = :uid AND kp.status = 'active'"
    params: dict = {"uid": user.id, "offset": (page - 1) * size, "size": size}
    if document_id:
        where += " AND kp.document_id = :did"
        params["did"] = document_id

    total = (
        await db.execute(
            text(f"SELECT count(*) FROM knowledge_points kp WHERE {where}"), params
        )
    ).scalar()
    rows = (
        await db.execute(
            text(
                f"""
                SELECT kp.id, kp.title, kp.summary, kp.difficulty, kp.importance, kp.keywords,
                       rr.due_at, rr.reps, rr.state, rr.stability, rr.retrievability
                FROM knowledge_points kp
                LEFT JOIN review_records rr ON rr.knowledge_point_id = kp.id
                WHERE {where}
                ORDER BY kp.importance DESC, kp.id
                LIMIT :size OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": r["id"],
                "title": r["title"],
                "summary": r["summary"],
                "difficulty": r["difficulty"],
                "importance": r["importance"],
                "keywords": r["keywords"] or [],
                "round": (r["reps"] or 0) + 1,
                "state": r["state"] or "new",
                "due_at": r["due_at"].isoformat() if r["due_at"] else None,
                "retrievability": round(float(r["retrievability"] or 1.0), 3),
            }
            for r in rows
        ],
    }


@router.get("/debug/search")
async def debug_search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(6, ge=1, le=20),
    user: User = Depends(get_demo_user),  # 调试端点仅演示账号
    db: AsyncSession = Depends(get_db),
):
    """返回向量/关键词/RRF 融合三个通道的检索结果，用于切块策略对比实验。"""
    result = await hybrid_search(db, user.id, q, top_k)
    for ch in ("vector", "keyword", "fused"):
        for item in result[ch]:
            item["content"] = item["content"][:120]
    return {"query": q, **result}


@router.get("/stats/overview")
async def stats_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统计页数据源：热力图、保有率、错因 Top5。"""
    heat = (
        await db.execute(
            text(
                "SELECT stat_date, reviews_done, avg_score FROM daily_stats "
                "WHERE user_id=:uid AND stat_date >= CURRENT_DATE - INTERVAL '90 days' ORDER BY stat_date"
            ),
            {"uid": user.id},
        )
    ).mappings().all()
    error_top = (
        await db.execute(
            text(
                "SELECT tag, count(*) AS n FROM ("
                "  SELECT jsonb_array_elements_text(error_tags) AS tag FROM quiz_responses "
                "  WHERE user_id=:uid AND jsonb_typeof(error_tags) = 'array'"
                ") t GROUP BY tag ORDER BY n DESC LIMIT 5"
            ),
            {"uid": user.id},
        )
    ).mappings().all()
    retention = (
        await db.execute(
            text(
                "SELECT round(avg(retrievability)::numeric, 3) AS avg_r, count(*) AS n "
                "FROM review_records WHERE user_id=:uid"
            ),
            {"uid": user.id},
        )
    ).mappings().first()
    kp_total = (
        await db.execute(
            text("SELECT count(*) FROM knowledge_points WHERE user_id=:uid AND status='active'"),
            {"uid": user.id},
        )
    ).scalar()
    return {
        "heat": [{"date": r["stat_date"].isoformat(), "count": r["reviews_done"], "avg_score": float(r["avg_score"] or 0)} for r in heat],
        "error_top": [{"tag": r["tag"], "count": r["n"]} for r in error_top],
        "retention": {"avg_retrievability": float(retention["avg_r"] or 0), "cards": retention["n"] or 0},
        "kp_total": kp_total,
    }
