"""预置评审数据：导入预置课件并完成建卡（幂等，可重复执行）。

与 seed_demo.py 配合使用，评委登录演示账号即看到：
  - 一份已建好知识卡片的课件（解析 → 抽取 → 向量化 → FSRS 新卡，今日队列直接有内容）
用法（backend 容器内或本地 venv）:
    python -m scripts.seed_demo_data
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.document import Document
from app.models.user import User

DEMO_EMAIL = "demo@memoloop.cn"
PRESET_DIR = Path(__file__).resolve().parent.parent / "storage" / "preset"
STORAGE_ROOT = Path(__file__).resolve().parent.parent / "storage"

DEMO_USER_ID_PLACEHOLDER = -1


def _safe_title(name: str) -> str:
    stem = Path(name).stem or "未命名文档"
    return re.sub(r"[\s_]+", " ", stem).strip()[:200]


async def main() -> None:
    # ① 找演示账号
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
    if user is None:
        raise SystemExit("演示账号不存在，请先运行 python -m scripts.seed_demo")

    pdfs = sorted(PRESET_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"预置课件目录为空: {PRESET_DIR}")

    from app.api.documents import process_document
    from app.services.pipeline import build_document

    for pdf in pdfs:
        title = _safe_title(pdf.name)
        # ② 幂等：同用户同名文档已存在则跳过
        async with AsyncSessionLocal() as db:
            dup = (
                await db.execute(
                    select(Document.id).where(
                        Document.user_id == user.id, Document.title == title
                    )
                )
            ).scalar()
        if dup:
            print(f"[跳过] 已导入过: {title}")
            continue

        # ③ 复制到该用户的存储目录（与 upload_document 相同路径规则）
        user_dir = STORAGE_ROOT / str(user.id)
        user_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.pdf"
        stored = user_dir / stored_name
        stored.write_bytes(pdf.read_bytes())

        async with AsyncSessionLocal() as db:
            doc = Document(
                user_id=user.id,
                title=title,
                file_name=pdf.name,
                file_type="pdf",
                file_size=pdf.stat().st_size,
                status="uploaded",
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)

        # ④ 同步执行完整流水线：解析切块 → 抽取建卡 → 向量化 → FSRS 新卡
        print(f"[导入] {title} (doc={doc.id}) → 解析切块…")
        await process_document(doc.id, str(stored), "pdf")
        async with AsyncSessionLocal() as db:
            d = (
                await db.execute(select(Document).where(Document.id == doc.id))
            ).scalar()
            print(f"  解析完成 status={d.status}")
            if d.status != "chunked":
                raise SystemExit(f"解析失败: {d.parse_error}")

        print("  抽取建卡中（真实 LLM 调用，需 1~3 分钟）…")
        await build_document(doc.id)
        async with AsyncSessionLocal() as db:
            d = (
                await db.execute(select(Document).where(Document.id == doc.id))
            ).scalar()
            print(f"  建卡完成 status={d.status}")

    # ⑤ 汇总
    from sqlalchemy import func, text

    async with AsyncSessionLocal() as db:
        kps = (
            await db.execute(
                text(
                    "SELECT count(*) FROM knowledge_points WHERE user_id = :uid"
                ),
                {"uid": user.id},
            )
        ).scalar()
        rrs = (
            await db.execute(
                text("SELECT count(*) FROM review_records WHERE user_id = :uid"),
                {"uid": user.id},
            )
        ).scalar()
    print(f"\n预置完成：演示账号共 {kps} 张知识卡、{rrs} 条 FSRS 记录（今日队列即刻可用）")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
