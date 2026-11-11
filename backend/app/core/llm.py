"""LLM / Embedding 统一客户端（OpenAI 协议兼容，硅基流动等）。

特性：批量 embedding、指数退避重试、JSON 模式、流式 chat(SSE 逐块产出)。
密钥与 base_url 全部来自环境变量。
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import httpx

from app.core.config import settings

MAX_RETRIES = 2


class LLMError(Exception):
    pass


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def chat(
    messages: list[dict],
    *,
    json_mode: bool = False,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    model: str | None = None,
) -> str:
    """非流式对话，返回完整文本。json_mode=True 时请求 response_format=json_object。"""
    payload: dict = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = await _post("/chat/completions", payload, settings.llm_base_url, settings.llm_api_key)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"LLM 响应结构异常: {str(data)[:200]}") from e


async def chat_stream(
    messages: list[dict],
    *,
    temperature: float = 0.5,
    max_tokens: int = 2048,
    model: str | None = None,
) -> AsyncIterator[str]:
    """流式对话：逐块 yield 文本增量。"""
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=30)) as client:
        async with client.stream("POST", url, json=payload, headers=_headers(settings.llm_api_key)) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode(errors="ignore")
                raise LLMError(f"LLM 流式调用失败 {resp.status_code}: {body[:300]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if delta:
                    yield delta


async def embed(texts: list[str]) -> list[list[float]]:
    """批量向量化，自动按 64 条分批。"""
    all_vecs: list[list[float]] = []
    for i in range(0, len(texts), 64):
        batch = [t[:8000] for t in texts[i : i + 64]]
        data = await _post(
            "/embeddings",
            {"model": settings.embedding_model, "input": batch},
            settings.embedding_base_url,
            settings.embedding_api_key,
        )
        # 按 index 还原顺序
        all_vecs.extend([None] * len(batch))  # type: ignore[arg-type]
        for item in data["data"]:
            all_vecs[i + item["index"]] = item["embedding"]
    return all_vecs


async def _post(path: str, payload: dict, base_url: str, key: str) -> dict:
    """带指数退避的 POST。"""
    url = base_url.rstrip("/") + path
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=20)) as client:
                resp = await client.post(url, json=payload, headers=_headers(key))
            if resp.status_code == 200:
                return resp.json()
            # 429/5xx 才重试，4xx 直接抛
            if resp.status_code not in (429, 500, 502, 503, 504):
                raise LLMError(f"{path} 失败 {resp.status_code}: {resp.text[:300]}")
            last_err = LLMError(f"{path} {resp.status_code}")
        except httpx.HTTPError as e:
            last_err = e
        if attempt < MAX_RETRIES:
            await asyncio.sleep(1.5 * (2**attempt))
    raise LLMError(f"重试后仍失败: {last_err}")


async def chat_json(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model: str | None = None,
) -> dict:
    """要求 JSON 输出并解析；解析失败抛 LLMError（调用方决定重试/降级）。"""
    raw = await chat(messages, json_mode=True, temperature=temperature, max_tokens=max_tokens, model=model)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM 输出非法 JSON: {raw[:200]}") from e
