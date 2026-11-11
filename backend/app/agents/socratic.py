"""Socratic Agent（P8）：围绕错因标签的定向追问（真·LLM 流式输出）。"""
from __future__ import annotations

from app.core.constants import ERROR_TAGS
from app.core.llm import chat_stream

SOCRATIC_PROMPT = """你是温和的苏格拉底式导师，正在带学生补"答错的知识点"。

【知识点】{title}
【本次要补的错因】{tags}
【对话历史】
{history}

规则：
1. 只围绕上述错因追问，一次只问一个问题；不直接给答案，用引导性问题让学生自己想通；
2. 学生答对 → 确认并推进到下一个错因；全部错因补完或问满 5 轮 → 总结收束（以"【收束】"开头写2句总结）；
3. 同一错因学生已错过两次 → 换一个新角度的问法，不要重复原问题；
4. 全程中文，每次回复不超过 120 字。"""


def build_messages(title: str, tags: list[str], history: list[dict]) -> list[dict]:
    hist = "\n".join(f"{'学生' if m['role'] == 'user' else '导师'}：{m['content'][:200]}" for m in history[-10:]) or "（开始对话）"
    return [
        {"role": "system", "content": SOCRATIC_PROMPT.format(title=title, tags="、".join(tags) or "综合理解", history=hist)},
    ]


async def socratic_reply(title: str, tags: list[str], history: list[dict]):
    """异步生成器：逐块 yield 文本增量（真流式）。"""
    messages = build_messages(title, tags, history) + [
        {"role": "user", "content": history[-1]["content"] if history and history[-1]["role"] == "user" else "请开始第一个引导性提问。"}
    ]
    async for delta in chat_stream(messages, temperature=0.4, max_tokens=400):
        yield delta


def is_concluded(text: str) -> bool:
    """判定本轮是否已收束。"""
    return "【收束】" in text
