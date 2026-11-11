"""FSRS 调度服务（P5）：今日队列、评级更新、可提取性计算。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fsrs import Card, Rating, Scheduler

from app.core.constants import quiz_type_for_round
from app.models.knowledge import KnowledgePoint, ReviewLog, ReviewRecord

# FSRS-5 记忆可提取性公式常数：R(t,S) = (1 + FACTOR·t/S)^DECAY
_DECAY = -0.5
_FACTOR = 19.0 / 81.0
scheduler = Scheduler()


def retrievability_from(stability: float, last_reviewed: Optional[datetime]) -> float:
    if not last_reviewed or stability <= 0:
        return 1.0
    days = (datetime.now(timezone.utc) - last_reviewed).total_seconds() / 86400
    if days < 0:
        days = 0
    return max(0.0, min(1.0, (1.0 + _FACTOR * days / stability) ** _DECAY))


def _state_to_fsrs(state: str):
    from fsrs import State

    return {"new": State.Learning, "learning": State.Learning, "review": State.Review, "relearning": State.Relearning}.get(state, State.Learning)


def _fsrs_state_to_str(state) -> str:
    return state.name.lower()  # learning / review / relearning


def _record_to_card(rec: ReviewRecord) -> Card:
    # 新卡没有有效的记忆状态，交给 FSRS 默认初始化（避免 stability=0 的除零）
    if rec.state == "new" or rec.reps == 0 or rec.stability <= 0:
        return Card()
    return Card(
        state=_state_to_fsrs(rec.state),
        step=0,
        stability=rec.stability,
        difficulty=rec.difficulty,
        due=rec.due_at or datetime.now(timezone.utc),
        last_review=rec.last_reviewed_at,
    )


async def today_queue(db: AsyncSession, user_id: int, limit: int = 20) -> list[dict]:
    """到期优先（按 due_at 升序），不足补新卡。返回卡片元数据（不含题目）。"""
    due_rows = (
        await db.execute(
            select(ReviewRecord, KnowledgePoint)
            .join(KnowledgePoint, ReviewRecord.knowledge_point_id == KnowledgePoint.id)
            .where(
                ReviewRecord.user_id == user_id,
                KnowledgePoint.status == "active",
                ReviewRecord.state != "new",
                ReviewRecord.due_at <= func.now(),
            )
            .order_by(ReviewRecord.due_at)
            .limit(limit)
        )
    ).all()

    items = [_queue_item(rec, kp) for rec, kp in due_rows]
    if len(items) < limit:
        new_rows = (
            await db.execute(
                select(ReviewRecord, KnowledgePoint)
                .join(KnowledgePoint, ReviewRecord.knowledge_point_id == KnowledgePoint.id)
                .where(
                    ReviewRecord.user_id == user_id,
                    KnowledgePoint.status == "active",
                    ReviewRecord.state == "new",
                )
                .order_by(KnowledgePoint.importance.desc(), KnowledgePoint.id)
                .limit(limit - len(items))
            )
        ).all()
        items += [_queue_item(rec, kp, is_new=True) for rec, kp in new_rows]
    return items


def _queue_item(rec: ReviewRecord, kp: KnowledgePoint, is_new: bool = False) -> dict:
    return {
        "kp_id": kp.id,
        "title": kp.title,
        "summary": kp.summary,
        "difficulty": kp.difficulty,
        "importance": kp.importance,
        "round": rec.reps + 1,
        "quiz_type": quiz_type_for_round(rec.reps + 1),
        "retrievability": round(rec.retrievability, 3),
        "state": rec.state,
        "due_at": rec.due_at.isoformat() if rec.due_at else None,
        "is_new": is_new,
    }


async def grade_review(
    db: AsyncSession,
    user_id: int,
    knowledge_point_id: int,
    rating: int,
    quiz_item_id: int | None = None,
) -> dict:
    """按 FSRS 更新记忆状态并写日志/日统计。返回新状态摘要。"""
    rec = (
        await db.execute(
            select(ReviewRecord).where(
                ReviewRecord.user_id == user_id,
                ReviewRecord.knowledge_point_id == knowledge_point_id,
            )
        )
    ).scalar_one_or_none()
    if rec is None:
        raise LookupError("复习记录不存在")

    scheduled_at = rec.due_at
    card = _record_to_card(rec)
    new_card, _log = scheduler.review_card(card, Rating(rating))

    rec.stability = float(new_card.stability)
    rec.difficulty = float(new_card.difficulty)
    rec.state = _fsrs_state_to_str(new_card.state)
    rec.due_at = new_card.due
    rec.last_reviewed_at = datetime.now(timezone.utc)
    rec.reps += 1
    if rating == 1:
        rec.lapses += 1
    rec.retrievability = retrievability_from(rec.stability, rec.last_reviewed_at)

    db.add(
        ReviewLog(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            review_record_id=rec.id,
            review_round=rec.reps,
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
            actual_at=datetime.now(timezone.utc),
            rating=rating,
            quiz_item_id=quiz_item_id,
            new_stability=rec.stability,
            new_due_at=rec.due_at,
        )
    )
    await _touch_daily_stats(db, user_id)
    await db.commit()
    return {
        "kp_id": knowledge_point_id,
        "round": rec.reps,
        "state": rec.state,
        "stability": round(rec.stability, 2),
        "difficulty": round(rec.difficulty, 2),
        "retrievability": round(rec.retrievability, 3),
        "due_at": rec.due_at.isoformat(),
    }


async def _touch_daily_stats(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        text(
            "INSERT INTO daily_stats (user_id, stat_date, reviews_done) "
            "VALUES (:uid, CURRENT_DATE, 1) "
            "ON CONFLICT (user_id, stat_date) DO UPDATE SET reviews_done = daily_stats.reviews_done + 1"
        ),
        {"uid": user_id},
    )


async def advance_round(db: AsyncSession, user_id: int, knowledge_point_id: int) -> dict:
    """演示账号专用：手动推进复习轮次（用于视频里展示题型升级）。"""
    rec = (
        await db.execute(
            select(ReviewRecord).where(
                ReviewRecord.user_id == user_id,
                ReviewRecord.knowledge_point_id == knowledge_point_id,
            )
        )
    ).scalar_one_or_none()
    if rec is None:
        raise LookupError("复习记录不存在")
    rec.reps += 1
    await db.commit()
    return {"kp_id": knowledge_point_id, "round": rec.reps, "quiz_type": quiz_type_for_round(rec.reps)}
