"""追问会话路由（P8）：SSE 多轮苏格拉底对话 + 弱点聚合更新。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.socratic import is_concluded, socratic_reply
from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


async def _get_conversation(db: AsyncSession, conv_id: int, user: User):
    row = (
        await db.execute(
            text(
                "SELECT c.id, c.status, c.trigger_tags, c.knowledge_point_id, kp.title "
                "FROM conversations c JOIN knowledge_points kp ON kp.id = c.knowledge_point_id "
                "WHERE c.id = :id AND c.user_id = :uid"
            ),
            {"id": conv_id, "uid": user.id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail="会话不存在")
    return row


@router.get("/{conv_id}")
async def get_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """会话详情 + 消息历史（前端恢复追问抽屉用）。"""
    conv = await _get_conversation(db, conv_id, user)
    messages = (
        await db.execute(
            text("SELECT role, content, created_at FROM messages WHERE conversation_id=:id ORDER BY id"),
            {"id": conv_id},
        )
    ).mappings().all()
    return {
        "id": conv["id"],
        "status": conv["status"],
        "trigger_tags": conv["trigger_tags"],
        "title": conv["title"],
        "messages": [dict(m) for m in messages],
    }


@router.post("/{conv_id}/messages")
async def post_message(
    conv_id: int,
    payload: MessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式追问：保存用户消息 → 流式生成导师回复 → 落库 → 收束时更新弱点。"""
    conv = await _get_conversation(db, conv_id, user)
    if conv["status"] == "closed":
        raise HTTPException(409, detail="会话已收束，请开启新会话")

    # 会话轮次上限（5 轮）
    turn_count = (
        await db.execute(
            text("SELECT count(*) FROM messages WHERE conversation_id=:id AND role='assistant'"),
            {"id": conv_id},
        )
    ).scalar() or 0

    await db.execute(
        text("INSERT INTO messages (conversation_id, role, content) VALUES (:id, 'user', :c)"),
        {"id": conv_id, "c": payload.content},
    )
    await db.commit()

    history = [
        dict(m)
        for m in (
            await db.execute(
                text("SELECT role, content FROM messages WHERE conversation_id=:id ORDER BY id"),
                {"id": conv_id},
            )
        ).mappings().all()
    ]

    # 超上限：不调 LLM，直接收束
    if turn_count >= 5:
        closing = "【收束】本次补弱已达轮次上限。建议稍后再复习该知识点巩固。"
        await db.execute(
            text("INSERT INTO messages (conversation_id, role, content) VALUES (:id, 'assistant', :c)"),
            {"id": conv_id, "c": closing},
        )
        await db.execute(text("UPDATE conversations SET status='closed' WHERE id=:id"), {"id": conv_id})
        await db.commit()
        await _bump_weaknesses(db, user.id, conv["trigger_tags"] or [])

        async def short():
            yield f'data: {json.dumps({"type": "chunk", "text": closing}, ensure_ascii=False)}\n\n'
            yield f'data: {json.dumps({"type": "done", "closed": True}, ensure_ascii=False)}\n\n'

        return StreamingResponse(short(), media_type="text/event-stream")

    tags = [t for t in (conv["trigger_tags"] or [])]

    async def event_stream():
        def send(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        full = []
        async for delta in socratic_reply(conv["title"], tags, history):
            full.append(delta)
            yield send({"type": "chunk", "text": delta})

        reply = "".join(full)
        await db.execute(
            text("INSERT INTO messages (conversation_id, role, content) VALUES (:id, 'assistant', :c)"),
            {"id": conv_id, "c": reply},
        )
        closed = is_concluded(reply)
        if closed:
            await db.execute(text("UPDATE conversations SET status='closed' WHERE id=:id"), {"id": conv_id})
            await db.commit()
            await _bump_weaknesses(db, user.id, tags)
        yield send({"type": "done", "closed": closed})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _bump_weaknesses(db: AsyncSession, user_id: int, tags: list[str]) -> None:
    """会话收束：把错因聚合进 learning_profiles.weaknesses（计数递增）。"""
    if not tags:
        return
    existing = (
        await db.execute(
            text("SELECT weaknesses FROM learning_profiles WHERE user_id=:uid"), {"uid": user_id}
        )
    ).scalar()
    items: list[dict] = [
        {"tag": w.get("tag") if isinstance(w, dict) else str(w),
         "count": w.get("count", 1) if isinstance(w, dict) else 1}
        for w in (existing or [])
    ]
    index = {it["tag"]: i for i, it in enumerate(items)}
    for tag in tags:
        if tag in index:
            items[index[tag]]["count"] += 1
        else:
            items.append({"tag": tag, "count": 1})
    items.sort(key=lambda x: -x["count"])
    items = items[:20]  # 只保留 Top20
    await db.execute(
        text(
            "INSERT INTO learning_profiles (user_id, weaknesses) VALUES (:uid, CAST(:w AS jsonb)) "
            "ON CONFLICT (user_id) DO UPDATE SET weaknesses = CAST(:w2 AS jsonb), updated_at = now()"
        ),
        {"uid": user_id, "w": json.dumps(items, ensure_ascii=False), "w2": json.dumps(items, ensure_ascii=False)},
    )
    await db.commit()
