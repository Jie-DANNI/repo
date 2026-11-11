"""Scorer Agent（P7）：rubric 评分 + 错因标签（固定词表）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from app.core.constants import ERROR_TAGS
from app.core.llm import LLMError, chat_json

SCORER_PROMPT = """你是阅卷官。依据"评分量规(rubric)"对学生作答逐点评分，并从固定词表选择错因标签。

【知识点】{title}
【参考答案】{answer}

【评分量规】
{rubric}

【学生作答】
{response}

输出 JSON：
{{"per_point": [{{"point": "量规要点原文", "hit": true或false, "comment": "简短点评"}}], "score": 0到1的浮点数(命中要点加权得分), "error_tags": ["从下方词表选择的标签", ...], "feedback": "综合反馈(80字内，指出具体缺失)"}}

错因标签只能从这个词表选择，禁止自造：{tags}
若学生答得很好，error_tags 为空数组。"""


class ScoreResult(BaseModel):
    per_point: list[dict] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)
    error_tags: list[str] = Field(default_factory=list)
    feedback: str = ""


async def score_answer(
    kp_title: str,
    answer: str | None,
    rubric: list[dict],
    response: str,
    is_objective: bool = False,
) -> ScoreResult:
    """客观题直接比对；主观题走 LLM rubric 评分。"""
    if is_objective:
        hit = response.strip() == (answer or "").strip()
        return ScoreResult(
            per_point=[{"point": "客观答案比对", "hit": hit, "comment": ""}],
            score=1.0 if hit else 0.0,
            error_tags=[] if hit else ["概念混淆"],
            feedback="答案正确。" if hit else f"正确答案：{answer}",
        )

    rubric_text = "\n".join(f"- {r['point']}（权重 {r['weight']}）" for r in rubric)
    messages = [
        {"role": "system", "content": "你是公正的阅卷官，只输出合法 JSON。"},
        {
            "role": "user",
            "content": SCORER_PROMPT.format(
                title=kp_title,
                answer=answer or "(无参考答案，依据知识点内容评分)",
                rubric=rubric_text or "- 覆盖知识点核心要点（权重 1.0）",
                response=response[:3000],
                tags="、".join(ERROR_TAGS),
            ),
        },
    ]
    last_err: Exception | None = None
    for _ in range(3):
        try:
            raw = await chat_json(messages, temperature=0.1, max_tokens=1200)
            result = ScoreResult(**raw)
            # 错因标签过滤：只保留词表内
            result.error_tags = [t for t in result.error_tags if t in ERROR_TAGS]
            return result
        except (LLMError, ValidationError, TypeError) as e:
            last_err = e
            messages.append({"role": "user", "content": f"上次输出无效({e})，请严格输出合法 JSON。"})
    # 评分失败降级：按内容长度给保守分，不打断闭环
    rough = min(0.6, len(response) / 400)
    return ScoreResult(
        per_point=[], score=round(rough, 2), error_tags=[],
        feedback=f"评分服务暂不可用，已按提交内容保守计分({round(rough,2)})。{last_err}",
    )
