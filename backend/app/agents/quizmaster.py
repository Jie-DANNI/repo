"""Quizmaster Agent（P6）：按复习轮次 × 记忆状态生成"升级题型"。

题型随轮次演变（创新点①）：
  round1 recognition（判断/填空）→ round2 choice（选择+常见误解干扰项）
  → round3 scenario（结合弱项的情景应用）→ round4+ feynman（费曼式讲解）
生成后经 SSE 流式下发：meta → question 逐块 → done(含结构化数据与 quiz_item_id)。
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field, ValidationError

from app.core.constants import ERROR_TAGS
from app.core.llm import LLMError, chat_json

RUBRIC_POINT = {"point": "要点描述", "weight": 0.3}


class QuizData(BaseModel):
    question: str = Field(min_length=8)
    quiz_type: str
    options: list[dict] | None = None   # [{"id":"A","text":"..."}]
    answer: str | None = None           # 正确选项id或填空答案
    rubric: list[dict] = Field(default_factory=list)  # [{point, weight}]
    explanation: str = ""


PROMPT_TEMPLATES = {
    "recognition": """轮次=1（识别阶段）。出"识别题"：判断题或关键词填空。
要求：
- question 中给出一句话陈述（判断题需一半概率为错误陈述，错误方式：偷换概念/改变范围/因果倒置）或挖掉1-2个关键词的填空句（用____表示空位）；
- options 省略或 null；answer 给出正确判断（"正确"/"错误"）或填空答案；
- rubric 省略。""",
    "choice": """轮次=2（理解阶段）。出"四选一"。
要求：
- 四个干扰项必须来自学习者对该知识点的常见误解（凭你对学科的理解构造，至少一个"部分正确但偷换条件"的强干扰项）；
- options 数组 4 项，每项 {{"id":"A"~"D","text":"..."}}；
- answer 为正确选项 id；rubric 给 2-3 个要点，weight 合计=1。""",
    "scenario": """轮次=3（应用阶段）。出"情景应用题"。
要求：
- 结合学习者弱项历史（下方"学习者弱点"），构造真实场景中的决策/分析问题，问"为什么/怎么做"；
- 不得照抄原文，必须要求迁移应用；
- rubric 给 3-4 个要点 {point, weight}，weight 合计=1，按重要性分配。""",
    "feynman": """轮次>=4（内化阶段）。出"费曼式讲解题"。
要求：
- question 形如："假设听众是完全零基础的{某个具体角色}，请把 {知识点标题} 讲明白，要求至少一个自己的类比和一个常见误区提醒"；
- rubric 侧重：概念完整、因果正确、类比恰当、误区提醒到位，3-4 个要点 weight 合计=1。""",
}


def build_quiz_prompt(kp: dict, quiz_type: str, round_: int, error_history: list[str], weaknesses: list[str]) -> str:
    tp = PROMPT_TEMPLATES.get(quiz_type, PROMPT_TEMPLATES["feynman"])
    err = "、".join(error_history[:6]) or "无"
    weak = "、".join(weaknesses[:6]) or "无"
    return f"""你是出题官（Quizmaster），为间隔复习系统出题，只输出 JSON。

【知识点卡片】
标题：{kp["title"]}
内容：{kp["content"]}

【学习者最近答错的点】{err}
【学习者长期弱点】{weak}

{tp}

输出 JSON 格式：
{{"question": "...", "quiz_type": "{quiz_type}", "options": [...] 或 null, "answer": "...", "rubric": [{{"point": "...", "weight": 0.3}}], "explanation": "考点解析(50字内)"}}

规则：题目语言为中文；question 必须自包含（不依赖上文）；rubric 的 weight 总和必须约等于 1。"""


async def generate_quiz(kp: dict, round_: int, quiz_type: str, error_history: list[str], weaknesses: list[str]) -> QuizData:
    """生成题目，校验失败重试 2 次。"""
    messages = [
        {"role": "system", "content": "你是严谨的出题官，只输出合法 JSON。"},
        {"role": "user", "content": build_quiz_prompt(kp, quiz_type, round_, error_history, weaknesses)},
    ]
    last_err: Exception | None = None
    for _ in range(3):
        try:
            raw = await chat_json(messages, temperature=0.4, max_tokens=1600)
            raw.setdefault("quiz_type", quiz_type)
            data = QuizData(**raw)
            # rubric weight 归一化兜底
            total = sum(float(r.get("weight", 0)) for r in data.rubric)
            if data.rubric and abs(total - 1.0) > 0.25:
                k = 1.0 / total if total > 0 else 1.0
                for r in data.rubric:
                    r["weight"] = round(float(r.get("weight", 0)) * k, 3)
            return data
        except (LLMError, ValidationError, TypeError) as e:
            last_err = e
            messages.append({"role": "user", "content": f"上次输出无效({e})，请严格输出合法 JSON。"})
    raise LLMError(f"出题重试后仍失败: {last_err}")


def fallback_quiz(kp: dict, quiz_type: str) -> QuizData:
    """LLM 彻底失败时的降级静态题，保证复习流程不中断。"""
    content = kp["content"][:200]
    if quiz_type == "recognition":
        return QuizData(
            question=f"填空：请补全以下表述中缺失的关键词。\n\n{content.replace(kp['title'], '____', 1) if kp['title'] in content else content}",
            quiz_type=quiz_type,
            answer=kp["title"],
            rubric=[{"point": "关键词还原正确", "weight": 1.0}],
            explanation="降级题目：AI 服务暂时不可用",
        )
    return QuizData(
        question=f"请用自己的话完整复述知识点「{kp['title']}」的要点并给出一个例子。",
        quiz_type=quiz_type,
        rubric=[{"point": "核心概念完整", "weight": 0.5}, {"point": "举例恰当", "weight": 0.5}],
        explanation="降级题目：AI 服务暂时不可用",
    )
