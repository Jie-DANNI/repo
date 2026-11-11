"""作答路由（P7）：提交答案 → rubric 评分 + 错因标签 → FSRS 闭环 → 触发追问会话。"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scorer import score_answer
from app.api.deps import get_current_user
from app.core.constants import score_to_rating
from app.db import get_db
from app.models.user import User
from app.services.review import grade_review

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class AnswerIn(BaseModel):
    answer_text: str | None = None
    selected_option: str | None = None  # 客观题选项 id，如 "B"


@router.post("/{quiz_item_id}/answer")
async def submit_answer(
    quiz_item_id: int,
    payload: AnswerIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交作答：评分 → 错因 → FSRS 评级 → 弱分自动创建追问会话。"""
    row = (
        await db.execute(
            text(
                "SELECT qi.id, qi.quiz_type, qi.question, qi.answer, qi.rubric, qi.knowledge_point_id, "
                "qi.options, kp.title, kp.user_id AS kp_owner "
                "FROM quiz_items qi JOIN knowledge_points kp ON kp.id = qi.knowledge_point_id "
                "WHERE qi.id = :id AND qi.user_id = :uid"
            ),
            {"id": quiz_item_id, "uid": user.id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail="题目不存在")

    if not (payload.answer_text or payload.selected_option):
        raise HTTPException(422, detail="答案不能为空")

    rubric = row["rubric"] or []
    is_objective = payload.selected_option is not None and row["quiz_type"] in ("recognition", "choice")

    response_content = payload.selected_option or (payload.answer_text or "")

    result = await score_answer(
        kp_title=row["title"],
        answer=row["answer"],
        rubric=rubric,
        response=response_content,
        is_objective=is_objective,
    )

    # 写 quiz_responses
    await db.execute(
        text(
            "INSERT INTO quiz_responses (quiz_item_id, user_id, answer_text, selected_option, "
            "score, error_tags, ai_feedback) "
            "VALUES (:qi, :uid, :ans, CAST(:opt AS jsonb), :score, CAST(:tags AS jsonb), :fb)"
        ),
        {
            "qi": quiz_item_id,
            "uid": user.id,
            "ans": payload.answer_text,
            "opt": json.dumps({"option": payload.selected_option}) if payload.selected_option else None,
            "score": result.score,
            "tags": json.dumps(result.error_tags, ensure_ascii=False),
            "fb": result.feedback,
        },
    )

    # FSRS 闭环
    rating = score_to_rating(result.score)
    fsrs = await grade_review(db, user.id, row["knowledge_point_id"], rating, quiz_item_id)

    # 弱分 → 自动创建定向追问会话
    conversation_id = None
    if result.score < 0.8 or result.error_tags:
        conversation_id = (
            await db.execute(
                text(
                    "INSERT INTO conversations (user_id, knowledge_point_id, quiz_item_id, trigger_tags) "
                    "VALUES (:uid, :kp, :qi, CAST(:tags AS jsonb)) RETURNING id"
                ),
                {
                    "uid": user.id,
                    "kp": row["knowledge_point_id"],
                    "qi": quiz_item_id,
                    "tags": json.dumps(result.error_tags, ensure_ascii=False),
                },
            )
        ).scalar()
        await db.commit()

    return {
        "score": round(result.score, 3),
        "rating": rating,
        "per_point": result.per_point,
        "error_tags": result.error_tags,
        "feedback": result.feedback,
        "fsrs": fsrs,
        "conversation_id": conversation_id,
        "answer": row["answer"] if result.score < 0.8 else None,  # 弱分才给参考答案
    }
