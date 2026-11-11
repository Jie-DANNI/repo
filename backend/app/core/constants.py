"""全局常量：错因标签词表（P7 评分输出、P8 定向追问的公共语言）。

★ 设计原则：LLM 只能从该词表选择，禁止自造标签——这是错因数据可统计、可回流的前提。
"""
ERROR_TAGS = [
    "概念混淆",
    "边界条件缺失",
    "公式误用",
    "因果倒置",
    "表述不严谨",
    "举例不当",
    "遗漏关键前提",
    "度量单位错误",
    "范围过度泛化",
]

# FSRS rating ↔ 分数换算（P7）
SCORE_TO_RATING = [(0.9, 4), (0.7, 3), (0.4, 2), (0.0, 1)]  # [(阈值以上, rating)] 从高到低


def score_to_rating(score: float) -> int:
    for threshold, rating in SCORE_TO_RATING:
        if score >= threshold:
            return rating
    return 1


# 复习轮次 → 题型等级（创新点①的核心映射）
ROUND_QUIZ_TYPE = {1: "recognition", 2: "choice", 3: "scenario"}


def quiz_type_for_round(round_: int) -> str:
    if round_ <= 0:
        return "recognition"
    if round_ in ROUND_QUIZ_TYPE:
        return ROUND_QUIZ_TYPE[round_]
    return "feynman"  # round>=4
