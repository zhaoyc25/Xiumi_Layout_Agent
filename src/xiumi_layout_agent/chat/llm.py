"""LLM 适配层：统一 chat(messages) -> str。真实实现走 [OI] 兼容接口，测试用 MockLLM。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from openai import OpenAI

from .config import LLMConfig, load_llm_config


class LLMClient(Protocol):
    def chat(self, messages: list[dict]) -> str: ...


class OpenAICompatLLM:
    """[OI] 兼容接口适配（如 [OI] / GLM / DeepSeek 等）。"""

    def __init__(self, cfg: LLMConfig):
        self._model = cfg.model
        self._client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    def chat(self, messages: list[dict]) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return resp.choices[0].message.content or ""


class MockLLM:
    """离线 mock：按脚本顺序返回固定回复。用于测试与无 Key 环境。"""

    def __init__(self, replies: list[str] | None = None):
        self.replies = list(replies or [])
        self.calls: list[list[dict]] = []
        self._fallback: Callable[[list[dict]], str] | None = None

    def on_message(self, fn: Callable[[list[dict]], str]) -> None:
        """设置动态应答函数（优先于脚本）。"""
        self._fallback = fn

    def chat(self, messages: list[dict]) -> str:
        self.calls.append([dict(m) for m in messages])
        if self._fallback is not None:
            return self._fallback(messages)
        if self.replies:
            return self.replies.pop(0)
        return "（mock：脚本已用完）"


def create_llm() -> LLMClient:
    """工厂：有配置用真实 LLM，否则抛错（调用方应引导用 MockLLM）。"""
    cfg = load_llm_config()
    if cfg is None:
        raise RuntimeError(
            "未找到 LLM 配置。请复制 secrets.example/config.env.example "
            "为 secrets/config.env 并填写，或在测试中使用 MockLLM。"
        )
    return OpenAICompatLLM(cfg)
