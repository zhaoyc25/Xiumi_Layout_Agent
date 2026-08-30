"""文字稿清洗：全角空格→半角、\\r\\n→\\n、去 Word 脏字符、压缩空行。

纯规则，零 LLM。处理文字稿的机械性脏污，语义层面的清洗交给 LLM（level.py）。
"""

from __future__ import annotations

import re

# Word/网页粘贴常见的零宽与控制字符
_ZEROWIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
# 多个连续空行压缩到最多 2 个
_MULTIBLANK = re.compile(r"\n{4,}")
# 行尾空白
_TRAILING = re.compile(r"[ \t]+$", re.MULTILINE)
# 全角空格
_FULLSPACE = "\u3000"


def clean_text(raw: str) -> str:
    """清洗原始文字稿，返回规范化文本。"""
    text = raw
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_FULLSPACE, " ")
    text = _ZEROWIDTH.sub("", text)
    text = _TRAILING.sub("", text)
    text = _MULTIBLANK.sub("\n\n\n", text)
    return text.strip()
