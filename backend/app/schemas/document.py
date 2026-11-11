"""文档与切块的响应模型。"""
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    file_name: str
    file_type: str
    file_size: int
    page_count: int | None
    status: str
    parse_error: str | None
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: int
    heading_path: str | None
    page_no: int | None
    token_count: int
    content: str
