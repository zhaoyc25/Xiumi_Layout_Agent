"""核心替换：按映射克隆模板节点 → 替换文字 → 清理图片 → 拼装 result.html。

全程固定 Python（BeautifulSoup），零 LLM。
所有 HTML 来自模板节点克隆，不手写任何标签/属性/样式（铁律）。
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from ..template.extract import LevelInfo, TemplateStructure


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

    # 层级号 → HTML 片段 + 是否"普通正文层"（可合并）
    level_html: dict[int, str] = {lv.level_id: lv.html_sample for lv in template.levels}
    level_plain: dict[int, bool] = {lv.level_id: _is_plain_body(lv) for lv in template.levels}

    # 相邻同 level 的"普通正文"块合并成一组（共用一个文本框，文字用 \n 拼接），
    # 标题层和特殊格式层（摘要/关键字/作者简介等带边框/背景）各自独立不合并
    groups: list[tuple[int, str]] = []
    for blk in leveled_draft:
        lv = blk.get("level", 0)
        text = blk.get("text", "")
        if lv not in level_html or not text:
            continue
        if groups and groups[-1][0] == lv and level_plain.get(lv):
            prev_lv, prev_text = groups[-1]
            groups[-1] = (prev_lv, prev_text + "\n" + text)
        else:
            groups.append((lv, text))

    # 新稿大标题 = 第一块文字（用于页面 <title> 和 <h1>）
    page_title = next((b.get("text", "") for b in leveled_draft if b.get("text")), "")

    for lv, text in groups:
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

    # 遗留问题：模板页面的 <title> / <h1> 还是旧标题，换成新稿大标题
    _fix_page_title(soup, page_title)

    return str(soup)


def _is_plain_body(lv: LevelInfo) -> bool:
    """普通正文层级：非标题，且无特殊背景/边框/投影（这些是摘要/关键字等特殊块）。"""
    if lv.is_heading:
        return False
    desc = lv.format_desc or ""
    return not re.search(r"(border|box-shadow|background-color|background-image)", desc)


def _fix_page_title(soup: BeautifulSoup, title: str) -> None:
    """把页面 <title> 和 <body> 内 <h1> 的文字换成新稿大标题（只改文字，不碰标签）。"""
    if not title:
        return
    t = soup.find("title")
    if t:
        t.string = title
    h1 = soup.body.find("h1") if soup.body else None
    if h1:
        h1.string = title


def _replace_text(clone: Tag, new_text: str) -> None:
    """替换克隆块里的文字：**加粗**→<b>、\\n→<br>，多段段首缩进，清残留空容器。

    模板正文层级常有多个 <p> 占位段落。若只删文字节点、留 <p> 壳，会留下
    一堆带 margin 的空 <p>（表现为正文后莫名多空行）。这里删文字时连其独占
    容器一起清理。
    """
    strings = [s for s in clone.find_all(string=True) if s.strip()]
    if not strings:
        return

    # Markdown → HTML，按段落拼装：多段时第二段起加段首缩进（全角空格），
    # 单段不缩进（标题/独立短句不缩进）
    paras = [re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p) for p in new_text.split("\n")]
    if len(paras) > 1:
        html_text = "<br>".join("　　" + p if p else p for p in paras)
    else:
        html_text = paras[0]

    parsed = BeautifulSoup(f"<div>{html_text}</div>", "lxml").find("div")

    # 第一个文字节点所在容器接收全部新内容
    container = strings[0].parent
    strings[0].extract()
    if parsed:
        for child in list(parsed.children):
            container.append(child.extract())

    # 其余文字节点：连其独占容器一起删（反复向上清理空壳），避免残留空 <p>
    for s in strings[1:]:
        parent = s.parent
        s.extract()
        _drop_empty_shell(parent)


def _drop_empty_shell(el: Tag | None) -> None:
    """元素无文字、无图片、无子 section 时删除，并向上清理一层空壳。

    模板标题/正文层级常残留空 <p><b></b></p>、<p><br></p> 占位壳（带 margin，
    表现为空行）。这里只要无文字、无 img、无子 section 就连同空 <b>/<span> 一起删。
    """
    while isinstance(el, Tag) and el.name in ("p", "span", "section", "b", "strong"):
        if el.get_text(strip=True):
            return
        if el.find(["img", "section"]):
            return
        parent = el.parent
        el.extract()
        el = parent


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
