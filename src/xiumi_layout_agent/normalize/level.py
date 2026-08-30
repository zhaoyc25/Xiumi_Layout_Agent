"""LLM 驱动的新稿分块+分级+映射：直调 llm.chat()，让 LLM 返回行号+层级号。

流程：
  ① 固定代码清洗文本（clean_text 已完成）
  ② 给 LLM：模板结构 + 带行号的全文
  ③ LLM 输出：每块从第几行到第几行、对应模板层级号（只有数字，输出极小）
  ④ 固定代码按行号切出原文，拼成 [{level, text}, ...]
"""

from __future__ import annotations

import json
import re

from ..chat.llm import LLMClient
from ..template.extract import TemplateStructure


def level_draft(text: str, template: TemplateStructure, llm: LLMClient) -> list[dict]:
    """让 LLM 把新稿分块、分级并映射到模板层级。

    返回 [{level: int, text: str}, ...]，level 为模板层级号（1, 2, 3...）。
    """
    lines = text.split("\n")
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))

    prompt = _build_prompt(numbered, len(lines), template)
    messages = [
        {"role": "system", "content": "你是文字稿分级助手。只输出 JSON 数组，不要输出其他内容。"},
        {"role": "user", "content": prompt},
    ]
    reply = llm.chat(messages)
    assignments = _parse_json(reply)

    result: list[dict] = []
    for a in assignments:
        from_line = int(a["from_line"]) - 1
        to_line = int(a["to_line"])
        from_line = max(0, from_line)
        to_line = min(len(lines), to_line)
        if from_line >= to_line:
            continue
        block_text = "\n".join(lines[from_line:to_line]).strip()
        if block_text:
            result.append({"level": int(a["level"]), "text": block_text})
    return result


def _build_prompt(numbered_text: str, line_count: int, template: TemplateStructure) -> str:
    """构造给 LLM 的 prompt：模板结构 + 带行号全文 + 输出要求。"""
    levels_desc = []
    for lv in template.levels:
        kind = "标题" if lv.is_heading else "正文"
        samples = "、".join(f'"{s[:20]}"' for s in lv.content_samples[:3])
        levels_desc.append(
            f"  层级{lv.level_id}：{lv.font_size}px {kind}"
            f"（样例：{samples}）"
        )
    levels_str = "\n".join(levels_desc)

    return f"""请把下面带行号的文字稿分成一块一块，每块标上对应的模板层级号。

模板结构（共{len(template.levels)}个层级）：
{levels_str}

要求：
1. 按内容把文字稿分成块（标题、正文段落、落款各自成块），每块覆盖连续的若干行
2. 每块对应模板的一个层级号（1 到 {len(template.levels)}）
3. 大标题对应字号最大的标题层级，正文段落对应正文字号的层级，落款对应最小字号的层级
4. 所有块的行范围要覆盖全文，不重叠、不遗漏

输出 JSON 数组，每项格式：
{{"level": 层级号, "from_line": 起始行号, "to_line": 结束行号（含）}}

带行号的文字稿（共{line_count}行）：
{numbered_text}"""


def _parse_json(reply: str) -> list[dict]:
    """从 LLM 回复中解析 JSON 数组，容错处理。"""
    text = reply.strip()
    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # 尝试提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    # 尝试提取第一个 [ ... ] 块
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"LLM 回复无法解析为 JSON 数组：{text[:200]}")
