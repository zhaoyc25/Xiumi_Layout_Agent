"""LLM 驱动的新稿分级+映射：发大纲（首尾句）给 LLM，只收层级号。

流程：
  ① 固定代码解析 Markdown 大纲（标题+正文首尾句），~1-3KB
  ② 给 LLM：模板结构 + 大纲（不含全文）
  ③ LLM 输出：每块对应模板层级号（只有数字，极小）
  ④ 固定代码拼回全文 → [{level, text}, ...]
"""

from __future__ import annotations

import json
import re

from ..chat.llm import LLMClient
from ..template.extract import TemplateStructure
from .outline import Block, parse_markdown, render_outline


def level_draft(md: str, template: TemplateStructure, llm: LLMClient) -> list[dict]:
    """让 LLM 把新稿大纲映射到模板层级，拼回全文。

    输入 md 为 Markdown 文本。返回 [{level: int, text: str}, ...]。
    """
    blocks = parse_markdown(md)
    if not blocks:
        return []

    outline = render_outline(blocks)
    prompt = _build_prompt(outline, len(blocks), template)
    messages = [
        {"role": "system", "content": "你是文字稿分级助手。只输出 JSON 数组，不要输出其他内容。"},
        {"role": "user", "content": prompt},
    ]
    reply = llm.chat(messages)
    assignments = _parse_json(reply)

    # 按 index 查找层级号
    level_map: dict[int, int] = {}
    for a in assignments:
        idx = int(a.get("index", 0))
        lv = int(a.get("level", 0))
        if idx and lv:
            level_map[idx] = lv

    # 拼回全文
    result: list[dict] = []
    for b in blocks:
        lv = level_map.get(b.index, _guess_level(b, template))
        result.append({"level": lv, "text": b.text})
    return result


def _guess_level(block: Block, template: TemplateStructure) -> int:
    """LLM 没标时的兜底：标题取最大标题层级，正文取最大正文层级。"""
    headings = [lv for lv in template.levels if lv.is_heading]
    bodies = [lv for lv in template.levels if not lv.is_heading]
    if block.kind == "heading":
        return headings[0].level_id if headings else 1
    return bodies[0].level_id if bodies else 1


def _build_prompt(outline: str, block_count: int, template: TemplateStructure) -> str:
    """构造给 LLM 的 prompt：模板结构 + 大纲 + 输出要求。"""
    levels_desc = []
    for lv in template.levels:
        kind = "标题" if lv.is_heading else "正文"
        samples = "、".join(f'"{s[:20]}"' for s in lv.content_samples[:3])
        levels_desc.append(
            f"  层级{lv.level_id}：{lv.font_size}px {kind}"
            f"（样例：{samples}）"
        )
    levels_str = "\n".join(levels_desc)

    return f"""请把下面的大纲每块标上对应的模板层级号。

模板结构（共{len(template.levels)}个层级）：
{levels_str}

新稿大纲（共{block_count}块）：
{outline}

要求：
1. 每块对应模板的一个层级号（1 到 {len(template.levels)}）
2. 大标题对应字号最大的标题层级，正文段落对应正文字号的层级
3. 根据 Markdown 层级（#越少层级越高）和内容判断

输出 JSON 数组，每项格式：
[{{"index": 1, "level": 1}}, {{"index": 2, "level": 2}}, ...]"""


def _parse_json(reply: str) -> list[dict]:
    """从 LLM 回复中解析 JSON 数组，容错处理。"""
    text = reply.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"LLM 回复无法解析为 JSON 数组：{text[:200]}")
