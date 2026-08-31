"""核心替换：按映射克隆模板节点 → 替换文字 → 清理图片 → 拼装 result.html。

全程固定 Python（BeautifulSoup），零 LLM。
所有 HTML 来自模板节点克隆，不手写任何标签/属性/样式（铁律）。
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from ..template.extract import TemplateStructure


def replace_template(
    html_path: Path,
    template: TemplateStructure,
    leveled_draft: list[dict],
) -> str:
    """按分级映射，克隆模板节点替换文字，生成 result.html。

    1. 加载模板 HTML，找到 <article> 下的根 <section>
    2. 删除原有内容块
    3. 逐块：克隆对应层级的 HTML 片段 → 清理图片 → 替换文字 → 追加
    4. 返回完整 HTML 字符串
    """
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    article = soup.find("article") or soup.body
    if not article:
        raise ValueError("模板 HTML 中找不到 <article> 或 <body>")
    root_sec = article.find("section")
    if not root_sec:
        raise ValueError("模板 HTML 中找不到根 <section>")

    # 删除原有内容块（直接子 section，保留 <p> 间隔等非 section 节点）
    for child in list(root_sec.children):
        if isinstance(child, Tag) and child.name == "section":
            child.extract()

    # 层级号 → HTML 片段
    level_html: dict[int, str] = {lv.level_id: lv.html_sample for lv in template.levels}

    # 逐块克隆+替换
    for blk in leveled_draft:
        lv = blk.get("level", 0)
        text = blk.get("text", "")
        if lv not in level_html or not text:
            continue

        clone = BeautifulSoup(level_html[lv], "lxml").find("section")
        if clone is None:
            continue

        # 所有克隆块都清理图片（新稿纯文字，模板里的图片都是旧内容）
        _clean_images(clone)

        _replace_text(clone, text)

        # 追加到根 section，用 <p> 间隔（跟模板风格一致）
        root_sec.append(clone)
        spacer = soup.new_tag("p")
        root_sec.append(spacer)

    return str(soup)


def _replace_text(clone: Tag, new_text: str) -> None:
    """替换克隆块里的文字，把 **加粗** 转成 <b>、\\n 转成 <br>。"""
    strings = [s for s in clone.find_all(string=True) if s.strip()]
    if not strings:
        return

    # Markdown → HTML
    html_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", new_text)
    html_text = html_text.replace("\n", "<br>")

    # 解析成 DOM 节点
    parsed = BeautifulSoup(f"<div>{html_text}</div>", "lxml").find("div")

    # 替换第一个文字节点所在的容器内容
    container = strings[0].parent
    strings[0].extract()
    if parsed:
        for child in list(parsed.children):
            container.append(child.extract())

    # 删掉其余文字节点
    for s in strings[1:]:
        s.extract()


def _clean_images(clone: Tag) -> None:
    """删除块内的图片节点（img），再迭代清除变空的包裹 section（不碰含文字的）。"""
    for img in clone.find_all("img"):
        img.extract()
    # 反复删除"无文字、无图片、无子 section"的空 section
    changed = True
    while changed:
        changed = False
        for sec in clone.find_all("section"):
            has_text = sec.get_text(strip=True)
            has_img = sec.find("img") is not None
            has_child = sec.find("section") is not None
            if not has_text and not has_img and not has_child:
                sec.extract()
                changed = True
