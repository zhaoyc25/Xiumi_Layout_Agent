"""LLM 配置读取：从 secrets/config.env / 环境变量加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_ENV = _REPO_ROOT / "secrets" / "config.env"


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str


def load_llm_config() -> LLMConfig | None:
    """读取 LLM 配置。缺任一项返回 None（此时必须用 MockLLM，不得硬编码 Key）。"""
    if _CONFIG_ENV.exists():
        load_dotenv(_CONFIG_ENV)
    api_key = os.environ.get("XIUMI_LLM_API_KEY", "")
    base_url = os.environ.get("XIUMI_LLM_BASE_URL", "")
    model = os.environ.get("XIUMI_LLM_MODEL", "")
    if not (api_key and base_url and model):
        return None
    return LLMConfig(api_key=api_key, base_url=base_url, model=model)
