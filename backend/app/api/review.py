"""复习路由（P5/P6）：今日队列、SSE 出题、评级、演示轮次推进。"""
import json
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.quizmaster import fallback_quiz, generate_quiz
from app.api.deps import get_current_user, get_demo_user
from app.core.config import settings
from app.core.constants import quiz_type_for_round
from app.db import get_db
from app.models.knowledge import KnowledgePoint, ReviewRecord
from app.models.user import User
from app.services.review import advance_round, grade_review, today_queue

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/today")
async def review_today(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """今日到期复习队列（按 due_at 升序，不足补新卡）。"""
    items = await today_queue(db, user.id, limit=limit)
    return {"total": len(items), "items": items}


class GradeIn(BaseModel):
    rating: int = Field(ge=1, le=4)  # 1=again 2=hard 3=good 4=easy
    quiz_item_id: int | None = None


@router.post("/{kp_id}/grade")
async def review_grade(
    kp_id: int,
    payload: GradeIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按 FSRS 评级更新记忆状态（P7 作答闭环内部也会调用）。"""
    try:
        result = await grade_review(db, user.id, kp_id, payload.rating, payload.quiz_item_id)
    except LookupError:
        raise HTTPException(404, detail="复习记录不存在")
    return result


@router.post("/{kp_id}/advance-round")
async def review_advance_round(
    kp_id: int,
    user: User = Depends(get_demo_user),  # 仅演示账号
    db: AsyncSession = Depends(get_db),
):
    """评审演示专用：手动推进复习轮次（视频里展示题型升级）。"""
    try:
        return await advance_round(db, user.id, kp_id)
    except LookupError:
        raise HTTPException(404, detail="复习记录不存在")


@router.post("/{kp_id}/quiz")
async def review_quiz(
    kp_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式出题：meta → question 逐块 → done。

    题目按当前轮次生成（recognition/choice/scenario/feynman），
    answer 与 rubric 仅落库不下发，防止"看答案再答"。
    """
    kp = (
        await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == kp_id, KnowledgePoint.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if kp is None:
        raise HTTPException(404, detail="知识点不存在")

    rec = (
        await db.execute(
            select(ReviewRecord).where(
                ReviewRecord.user_id == user.id, ReviewRecord.knowledge_point_id == kp_id
            )
        )
    ).scalar_one_or_none()
    round_ = (rec.reps + 1) if rec else 1
    quiz_type = quiz_type_for_round(round_)

    # 错因历史 + 长期弱点注入
    error_rows = (
        await db.execute(
            text(
                # 注意：只摊平一层。jsonb_array_elements_text 已经把数组展开成字符串，
                # 绝不能再对它套一次 jsonb_array_elements（会报 cannot extract elements from a scalar）
                "SELECT tag FROM ( "
                "  SELECT jsonb_array_elements_text(qr.error_tags) AS tag, qr.answered_at "
                "  FROM quiz_responses qr "
                "  JOIN quiz_items qi ON qi.id = qr.quiz_item_id "
                "  WHERE qi.knowledge_point_id = :kp AND qr.user_id = :uid "
                "    AND jsonb_typeof(qr.error_tags) = 'array' "
                "  ORDER BY qr.answered_at DESC "
                "  LIMIT 20 "
                ") t WHERE t.tag IS NOT NULL LIMIT 10"
            ),
            {"kp": kp_id, "uid": user.id},
        )
    ).scalars().all()
    weak_rows = (
        await db.execute(
            text("SELECT weaknesses FROM learning_profiles WHERE user_id = :uid"),
            {"uid": user.id},
        )
    ).scalar()
    weaknesses = [w.get("tag", str(w)) if isinstance(w, dict) else str(w) for w in (weak_rows or [])]

    kp_dict = {"title": kp.title, "content": kp.content, "difficulty": kp.difficulty}
    t0 = time.perf_counter()
    try:
        data = await generate_quiz(kp_dict, round_, quiz_type, list(error_rows), weaknesses)
        used_fallback = False
    except Exception:  # noqa: BLE001 — 出题失败降级，复习不中断
        data = fallback_quiz(kp_dict, quiz_type)
        used_fallback = True
    latency_ms = round((time.perf_counter() - t0) * 1000)

    # 落库
    item_id = (
        await db.execute(
            text(
                "INSERT INTO quiz_items (knowledge_point_id, user_id, review_round, quiz_type, "
                "question, options, answer, rubric, explanation, generation_meta) "
                "VALUES (:kp, :uid, :round, :qt, :question, CAST(:options AS jsonb), :answer, "
                "CAST(:rubric AS jsonb), :explanation, CAST(:meta AS jsonb)) RETURNING id"
            ),
            {
                "kp": kp_id,
                "uid": user.id,
                "round": round_,
                "qt": quiz_type,
                "question": data.question,
                "options": json.dumps(data.options) if data.options else None,
                "answer": data.answer,
                "rubric": json.dumps(data.rubric),
                "explanation": data.explanation,
                "meta": json.dumps(
                    {
                        "model": settings.llm_model,
                        "prompt_version": 1,
                        "latency_ms": latency_ms,
                        "fallback": used_fallback,
                    }
                ),
            },
        )
    ).scalar()
    await db.commit()

    async def event_stream():
        def send(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        yield send({"type": "meta", "kp_id": kp_id, "round": round_, "quiz_type": quiz_type})
        # 服务端逐块下发题目文本（前端打字机渲染）
        text_ = data.question
        step = 8
        for i in range(0, len(text_), step):
            yield send({"type": "chunk", "text": text_[i : i + step]})
            time.sleep(0.02)
        yield send(
            {
                "type": "done",
                "quiz_item_id": item_id,
                "quiz_type": quiz_type,
                "options": data.options,
                "fallback": used_fallback,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
