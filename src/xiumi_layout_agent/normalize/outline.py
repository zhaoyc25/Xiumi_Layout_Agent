"""Markdown 大纲解析：固定程序提取标题+正文预览，供 LLM 做层级映射。

不调 LLM，纯规则。把 Markdown 文稿解析成块列表，每块带：
- 类型（标题/正文）
- Markdown 层级（#/##/### → 1/2/3，正文为 None）
- 预览（标题取全文，正文取前10字）
- 完整文字（保留，最后拼回用）
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Block:
    index: int
    kind: str               # "heading" / "body"
    md_level: int | None    # # =1, ## =2, ### =3；正文为 None
    preview: str            # 标题=全文；正文=首句…尾句
    text: str               # 完整文字（拼回用）


def parse_markdown(md: str) -> list[Block]:
    """解析 Markdown 文稿，返回块列表。"""
    lines = md.split("\n")
    blocks: list[Block] = []
    i = 0
    idx = 0

    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行和分隔线
        if not line or line == "---":
            i += 1
            continue

        # 标题：# / ## / ###
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            idx += 1
            level = len(m.group(1))
            text = m.group(2).strip()
            blocks.append(Block(
                index=idx, kind="heading", md_level=level,
                preview=text, text=text,
            ))
            i += 1
            continue

        # 正文：收集连续非空行直到下一个标题/分隔线/空行
        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt == "---" or re.match(r"^#{1,6}\s+", nxt):
                break
            para_lines.append(nxt)
            i += 1

        text = "\n".join(para_lines)
        idx += 1
        blocks.append(Block(
            index=idx, kind="body", md_level=None,
            preview=_preview_body(text), text=text,
        ))

    return blocks


def _preview_body(text: str) -> str:
    """正文取前10个字。"""
    return text[:10]


def render_outline(blocks: list[Block]) -> str:
    """把块列表渲染成紧凑的大纲文本（给 LLM 看）。"""
    lines = []
    for b in blocks:
        if b.kind == "heading":
            tag = f"标题{'#' * (b.md_level or 1)}"
        else:
            tag = "正文"
        lines.append(f"  {b.index}. [{tag}] {b.preview}")
    return "\n".join(lines)
