"""文档路由：上传 → 后台解析切块 → 列表/详情/切块预览/删除。"""
import math
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db import AsyncSessionLocal, get_db
from app.models.document import Chunk, Document
from app.models.user import User
from app.schemas.document import ChunkOut, DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {"pdf", "md", "txt"}
STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage"


def _safe_title(name: str) -> str:
    """从文件名剥扩展名得到标题，去掉常见杂质。"""
    stem = Path(name).stem or "未命名文档"
    return re.sub(r"[\s_]+", " ", stem).strip()[:200]


async def process_document(document_id: int, file_path: str, file_type: str) -> None:
    """后台任务：解析切块入库。独立会话，不依赖请求生命周期。"""
    from app.services.parser import parse_file

    async with AsyncSessionLocal() as db:
        doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
        if doc is None:
            return
        doc.status = "parsing"
        await db.commit()

        try:
            chunks, page_count = parse_file(file_path, file_type)
            if not chunks:
                raise ValueError("未能从文档中提取到任何文本（可能是纯图片扫描件）")

            doc.page_count = page_count
            doc.status = "chunked"
            db.add_all(
                [
                    Chunk(
                        document_id=document_id,
                        user_id=doc.user_id,
                        content=c.content,
                        heading_path=c.heading_path,
                        page_no=c.page_no,
                        token_count=c.token_count,
                    )
                    for c in chunks
                ]
            )
            doc.parse_error = None
        except Exception as e:  # noqa: BLE001 — 任何解析失败都要落库可查
            doc.status = "failed"
            doc.parse_error = str(e)[:2000]
        await db.commit()


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(422, detail=f"仅支持 {', '.join(sorted(ALLOWED_TYPES))} 格式")

    content = await file.read()
    if len(content) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(413, detail=f"文件超过 {settings.upload_max_mb}MB 上限")

    # 保存到 storage/{user_id}/{uuid}.{ext}
    user_dir = STORAGE_ROOT / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    (user_dir / stored_name).write_bytes(content)

    doc = Document(
        user_id=user.id,
        title=_safe_title(file.filename or "未命名文档"),
        file_name=file.filename or stored_name,
        file_type=ext,
        file_size=len(content),
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    background.add_task(process_document, doc.id, str(user_dir / stored_name), ext)
    return DocumentOut.model_validate(doc).model_copy(update={"chunk_count": 0})


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = (
        await db.execute(
            select(Document).where(Document.user_id == user.id).order_by(desc(Document.created_at))
        )
    ).scalars().all()
    out = []
    for d in docs:
        count = (
            await db.execute(select(func.count()).where(Chunk.document_id == d.id))
        ).scalar() or 0
        out.append(DocumentOut.model_validate(d).model_copy(update={"chunk_count": count}))
    return out


@router.get("/{document_id}/chunks", response_model=dict)
async def list_chunks(
    document_id: int,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切块分页预览，用于前端检查解析质量。"""
    doc = (
        await db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user.id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, detail="文档不存在")

    total = (
        await db.execute(select(func.count()).where(Chunk.document_id == document_id))
    ).scalar() or 0
    rows = (
        await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()
    return {
        "total": total,
        "page": page,
        "pages": math.ceil(total / size) if size else 0,
        "items": [
            ChunkOut(
                id=r.id,
                heading_path=r.heading_path,
                page_no=r.page_no,
                token_count=r.token_count,
                content=r.content,
            )
            for r in rows
        ],
    }


@router.post("/{document_id}/extract", status_code=202)
async def extract_knowledge(
    document_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """触发知识库构建流水线：向量补写 → Extractor 抽取 → 建 FSRS 记录。"""
    doc = (
        await db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user.id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, detail="文档不存在")
    if doc.status not in ("chunked", "extracted", "failed"):
        raise HTTPException(409, detail=f"当前状态 {doc.status} 不可构建（需先完成解析切块）")

    from app.services.pipeline import build_document

    background.add_task(build_document, document_id)
    return {"detail": "知识库构建已启动", "status": "extracting"}


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user.id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, detail="文档不存在")

    # 删除物理文件（best-effort）
    user_dir = STORAGE_ROOT / str(user.id)
    for f in user_dir.glob(f"*"):
        if f.name == doc.file_name or f.name.endswith(doc.file_name or ""):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass

    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    await db.delete(doc)
    await db.commit()
