"""文档解析与切块：结构感知（标题层级）切块，而非固定 token 暴力切。

输出块元数据：content / heading_path / page_no / token_count
策略：
- PDF：用字体大小（相对正文倍率）+ 编号样式识别标题，维护层级栈
- Markdown：按 # 层级
- TXT：按空行分段，无层级
目标块长 300-600 token（估算：CJK≈1 token/字，拉丁词≈1.3 token/词）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

HEADING_NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[\s、.．)）]+\S")
CHAPTER_RE = re.compile(r"^\s*(第[一二三四五六七八九十百\d]+[章节篇讲])\s*\S*")
MIN_CHUNK_TOKENS = 120   # 低于此值并入相邻块
MAX_CHUNK_TOKENS = 600
TARGET_CHUNK_TOKENS = 500


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：中文字符≈1 token，拉丁按词×1.3。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(re.findall(r"[A-Za-z]+[\w'.-]*", text))
    return cjk + int(other * 1.3) + len(re.findall(r"\d+", text))


@dataclass
class ParsedChunk:
    content: str
    heading_path: str | None = None
    page_no: int | None = None
    token_count: int = 0


@dataclass
class _HeadingStack:
    """标题层级栈：按级别压栈/弹栈，得到 '第1章 > 1.2 节' 形式的路径。"""
    stack: list[tuple[int, str]] = field(default_factory=list)

    def push(self, level: int, title: str) -> str:
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, title))
        return " > ".join(t for _, t in self.stack)

    def current(self) -> str | None:
        return " > ".join(t for _, t in self.stack) if self.stack else None


def _looks_like_heading(text: str, size: float, body_size: float, bold: bool) -> int | None:
    """判定是否为标题，返回层级（数字越小层级越高），非标题返回 None。"""
    t = text.strip()
    if not t or len(t) > 60:
        return None
    if CHAPTER_RE.match(t):
        return 1
    m = HEADING_NUM_RE.match(t)
    numbered = m is not None
    big = size >= body_size * 1.15
    if numbered:
        depth = m.group(1).count(".") + 1  # "3.2.1" → 层级3
        return depth
    if (big or bold) and len(t) <= 40 and not t.endswith(("。", "，", "；", "？", "！")):
        return 2 if big and size >= body_size * 1.45 else 3
    return None


def parse_pdf(path: str) -> tuple[list[ParsedChunk], int]:
    """解析 PDF：返回 (chunks, page_count)。"""
    doc = pymupdf.open(path)
    hs = _HeadingStack()
    blocks: list[tuple[str, int, str | None]] = []  # (text, page_no, heading_path)

    # 统计字号出现频次（按字符数加权）找正文基准字号
    size_counter: dict[float, int] = {}
    spans: list[tuple[float, bool, str, int]] = []
    for page_no, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    size = round(float(span.get("size", 12)), 1)
                    bold = bool(span.get("flags", 0) & 2 ** 4)
                    spans.append((size, bold, text, page_no))
                    size_counter[size] = size_counter.get(size, 0) + len(text)

    body_size = max(size_counter, key=size_counter.get) if size_counter else 12.0

    for size, bold, text, page_no in spans:
        level = _looks_like_heading(text, size, body_size, bold)
        if level is not None:
            hs.push(level, text)
            continue
        blocks.append((text, page_no, hs.current()))

    page_count = doc.page_count
    doc.close()
    return _merge_blocks(blocks), page_count


def parse_markdown(path: str) -> tuple[list[ParsedChunk], None]:
    """解析 Markdown：按 # 层级。"""
    hs = _HeadingStack()
    blocks: list[tuple[str, int, str | None]] = []
    buf: list[str] = []
    cur_page, cur_path = 1, None

    def flush() -> None:
        nonlocal buf
        if buf:
            blocks.append(("\n".join(buf), cur_page, cur_path))
            buf = []

    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            flush()
            level = len(m.group(1))
            cur_path = hs.push(level, m.group(2).strip())
        elif line.strip():
            buf.append(line.rstrip())
        else:
            flush()
    flush()
    return _merge_blocks(blocks), None


def parse_txt(path: str) -> tuple[list[ParsedChunk], None]:
    """纯文本：按空行分段。"""
    raw = open(path, encoding="utf-8", errors="ignore").read()
    blocks = [(p.strip(), 1, None) for p in re.split(r"\n\s*\n", raw) if p.strip()]
    return _merge_blocks(blocks), None


def _merge_blocks(blocks: list[tuple[str, int, str | None]]) -> list[ParsedChunk]:
    """把相邻块合并到目标长度；超长块按句子切分；产出 ParsedChunk 列表。"""
    chunks: list[ParsedChunk] = []
    buf_text: list[str] = []
    buf_path: str | None = None
    buf_page: int | None = None

    def flush() -> None:
        nonlocal buf_text
        if not buf_text:
            return
        text = "\n".join(buf_text).strip()
        if not text:
            buf_text = []
            return
        _append_with_split(chunks, text, buf_path, buf_page)
        buf_text = []

    for text, page_no, path in blocks:
        # 标题路径变化时先结算当前缓冲
        if buf_text and (path != buf_path):
            flush()
        if not buf_text:
            buf_path, buf_page = path, page_no
        buf_text.append(text)
        if estimate_tokens("\n".join(buf_text)) >= TARGET_CHUNK_TOKENS:
            flush()
    flush()

    # 合并过短的块到前一个（同路径才合并）
    merged: list[ParsedChunk] = []
    for c in chunks:
        if (
            merged
            and c.token_count < MIN_CHUNK_TOKENS
            and merged[-1].heading_path == c.heading_path
            and merged[-1].token_count + c.token_count <= MAX_CHUNK_TOKENS
        ):
            merged[-1].content += "\n" + c.content
            merged[-1].token_count += c.token_count
        else:
            merged.append(c)
    return merged


def _append_with_split(chunks: list[ParsedChunk], text: str, path: str | None, page: int | None) -> None:
    """单块超过上限时按句子拆分。"""
    if estimate_tokens(text) <= MAX_CHUNK_TOKENS:
        chunks.append(ParsedChunk(text, path, page, estimate_tokens(text)))
        return
    sentences = re.split(r"(?<=[。！？!?；;.])\s*", text)
    part: list[str] = []
    for s in sentences:
        part.append(s)
        if estimate_tokens("".join(part)) >= TARGET_CHUNK_TOKENS:
            chunks.append(ParsedChunk("".join(part), path, page, estimate_tokens("".join(part))))
            part = []
    if part:
        tail = "".join(part)
        if chunks and estimate_tokens(tail) < MIN_CHUNK_TOKENS:
            chunks[-1].content += tail
            chunks[-1].token_count += estimate_tokens(tail)
        else:
            chunks.append(ParsedChunk(tail, path, page, estimate_tokens(tail)))


def parse_file(path: str, file_type: str) -> tuple[list[ParsedChunk], int | None]:
    """统一入口。"""
    if file_type == "pdf":
        return parse_pdf(path)
    if file_type == "md":
        return parse_markdown(path)
    return parse_txt(path)
