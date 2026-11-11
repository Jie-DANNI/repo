"""知识库构建流水线（P3+P4 串联）：向量补写 → 分组抽取 → 建卡 → 建 FSRS 记录。"""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.extractor import group_chunks, run_extractor
from app.core.config import settings
from app.core.llm import LLMError
from app.db import AsyncSessionLocal
from app.models.document import Document
from app.models.knowledge import KnowledgePoint, ReviewRecord
from app.services.vectors import embed_chunks, set_kp_embedding


async def build_document(document_id: int) -> None:
    """后台任务：完整建库。状态机 chunked → extracting → extracted / failed。"""
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
        if doc is None or doc.status not in ("chunked", "extracted", "failed"):
            return

        doc.status = "extracting"
        await db.commit()

        try:
            from app.agents.extractor import record_prompt_version

            await record_prompt_version(db)

            # ① 向量补写（幂等）
            await embed_chunks(db, document_id)

            # ② 取切块，按顶层标题分组
            rows = (
                await db.execute(
                    text(
                        "SELECT id, content, heading_path, token_count "
                        "FROM chunks WHERE document_id = :did ORDER BY id"
                    ),
                    {"did": document_id},
                )
            ).mappings().all()
            chunk_dicts = [dict(r) for r in rows]
            if not chunk_dicts:
                raise ValueError("没有可用的切块")

            # ③ 逐组抽取
            created = 0
            for window in group_chunks(chunk_dicts):
                context = "\n\n".join(
                    f"【{(c.get('heading_path') or '正文')}】\n{c['content']}" for c in window
                )
                points, meta = await run_extractor(context)
                meta["model"] = settings.llm_model
                for p in points:
                    # 幂等：同文档同名卡片跳过
                    dup = (
                        await db.execute(
                            select(KnowledgePoint.id).where(
                                KnowledgePoint.document_id == document_id,
                                KnowledgePoint.title == p.title,
                            )
                        )
                    ).scalar()
                    if dup:
                        continue
                    kp = KnowledgePoint(
                        document_id=document_id,
                        user_id=doc.user_id,
                        title=p.title.strip(),
                        content=p.content.strip(),
                        summary=p.summary.strip(),
                        keywords=[k.strip() for k in p.keywords][:8],
                        difficulty=max(1, min(5, p.difficulty)),
                        importance=max(1, min(5, p.importance)),
                    )
                    db.add(kp)
                    await db.flush()
                    await set_kp_embedding(db, kp.id, kp.content)
                    db.add(
                        ReviewRecord(
                            user_id=doc.user_id,
                            knowledge_point_id=kp.id,
                            state="new",
                        )
                    )  # due_at 默认 now()，新卡立即进入今日队列
                    created += 1
                await db.commit()

            doc.status = "extracted"
            doc.parse_error = None
            await db.commit()
        except Exception as e:  # noqa: BLE001
            import traceback
            await db.rollback()
            doc = (
                await db.execute(select(Document).where(Document.id == document_id))
            ).scalar_one()
            doc.status = "failed"
            doc.parse_error = f"知识库构建失败: {str(e)[:800]}\nTRACE: {traceback.format_exc()[-1200:]}"
            await db.commit()
