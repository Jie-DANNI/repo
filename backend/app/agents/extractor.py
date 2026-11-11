"""Extractor Agent（P4）：文档切块 → 结构化知识点卡片。

- 按 heading_path 分组喂给 LLM，上下文限制在 ~3000 token
- 强制 JSON 输出 + Pydantic 校验 + 最多 2 次重试
- prompt 模板版本写入 prompt_versions（技术文档实证数据源）
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field, ValidationError

from app.core.llm import LLMError, chat_json
from app.services.parser import estimate_tokens

EXTRACT_PROMPT_V1 = """你是知识点抽取引擎。任务：从给定的课程资料片段中抽取"值得复习的知识点"。

输出严格 JSON，格式：
{{"points": [{{"title": "知识点标题(简短、可独立成卡)", "content": "卡片正面内容：定义/公式/结论的完整表述", "summary": "一句话摘要", "keywords": ["关键词1", "关键词2"], "difficulty": 1到5的整数, "importance": 1到5的整数}}]}}

规则：
1. 只抽取可独立复习的知识点；跳过目录、页眉页脚、过渡句、习题原文；
2. 同一概念只出一张卡，标题不可重复，标题不超过20字；
3. content 必须自包含（脱离原文也能看懂），含公式时保留公式原文；
4. difficulty=掌握难度（1易5难），importance=考纲/概念核心度（1边缘5核心），凭内容判断；
5. 若片段没有值得抽取的知识点，输出 {{"points": []}}，不要编造。

资料片段：
{context}"""


class ExtractedPoint(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    content: str = Field(min_length=10)
    summary: str = ""
    keywords: list[str] = Field(default_factory=list, max_length=8)
    difficulty: int = Field(ge=1, le=5)
    importance: int = Field(ge=1, le=5)


class ExtractionResult(BaseModel):
    points: list[ExtractedPoint]


def group_chunks(chunks: list[dict], max_tokens: int = 3000) -> list[list[dict]]:
    """按顶层标题聚合切块，组内超过 max_tokens 再切窗。"""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for c in chunks:
        key = (c.get("heading_path") or "正文").split(" > ")[0]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)

    windows: list[list[dict]] = []
    for key in order:
        current: list[dict] = []
        tokens = 0
        for c in groups[key]:
            t = c.get("token_count") or estimate_tokens(c["content"])
            if current and tokens + t > max_tokens:
                windows.append(current)
                current, tokens = [], 0
            current.append(c)
            tokens += t
        if current:
            windows.append(current)
    return windows


async def extract_points(context: str) -> list[ExtractedPoint]:
    """LLM 抽取 + 校验 + 重试。"""
    messages = [
        {"role": "system", "content": "你是知识点抽取引擎，只输出 JSON。"},
        {"role": "user", "content": EXTRACT_PROMPT_V1.format(context=context)},
    ]
    last_err: Exception | None = None
    for attempt in range(3):  # 初次 + 重试2次
        try:
            raw = await chat_json(messages, temperature=0.1, max_tokens=3072)
            result = ExtractionResult(**raw)
            # 标题去重（大小写不敏感）
            seen: set[str] = set()
            uniq = [p for p in result.points if not (k := p.title.strip().lower()) in seen and not seen.add(k)]
            return uniq
        except (LLMError, ValidationError, TypeError, KeyError) as e:
            last_err = e
            # 重试时降温
            messages.append({"role": "user", "content": f"上次输出无效({e})，严格按 JSON 格式重输。"})
    raise LLMError(f"知识点抽取重试后仍失败: {last_err}")


async def record_prompt_version(db) -> None:
    """把当前 prompt 版本写入 prompt_versions（幂等）。"""
    from sqlalchemy import text

    exists = (
        await db.execute(
            text("SELECT 1 FROM prompt_versions WHERE scene='extract' AND version=1")
        )
    ).scalar()
    if exists:
        return
    await db.execute(
        text(
            "INSERT INTO prompt_versions (scene, version, template, notes, metrics, active) "
            "VALUES ('extract', 1, :tpl, :notes, '{}', true)",
        ),
        {"tpl": EXTRACT_PROMPT_V1[:4000], "notes": "v1 初版：按 heading_path 分组、跳过习题原文、标题去重"},
    )
    await db.commit()


async def run_extractor(context: str) -> tuple[list[ExtractedPoint], dict]:
    """带计时的入口，返回 (points, generation_meta)。"""
    t0 = time.perf_counter()
    points = await extract_points(context)
    return points, {
        "model": None,  # 由调用方补
        "prompt_version": 1,
        "latency_ms": round((time.perf_counter() - t0) * 1000),
        "in_points": len(points),
    }
