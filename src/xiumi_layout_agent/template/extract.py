"""模板 HTML 结构提取：BeautifulSoup 按嵌入结构签名分组，产出层级信息。

核心思路：每个块的"嵌入格式"由外层 2 层 section 的样式决定（display/width/
color/background/text-align/border-radius 等），跟字号无关。
同签名 = 同层级；同字号不同结构 = 不同层级。

产出：标准格式文件（层级↔HTML 片段映射），供 LLM 映射 + M7 克隆使用。
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# 签名里要提取的样式属性（定义"嵌入格式"的关键属性）
_SIGN_KEYS = [
    "display", "text-align", "font-size", "color", "width",
    "background-color", "border-radius", "padding", "justify-content",
    "flex-flow", "vertical-align", "transform", "letter-spacing",
    "line-height",
]
_PEEK_LAYERS = 2  # 只看外层 2 层（定义嵌入格式，不看内部内容变化）
_MAX_CONTENT_SAMPLES = 4


def _layer_sig(el: Tag) -> tuple[str, ...]:
    """单层 section 的样式签名。"""
    style = el.get("style", "") or ""
    parts = []
    for k in _SIGN_KEYS:
        m = re.search(rf"{re.escape(k)}\s*:\s*([^;]+)", style)
        if m:
            parts.append(f"{k}={m.group(1).strip()[:25]}")
    return tuple(parts)


def _outer_sig(blk: Tag) -> tuple[tuple[str, ...], ...]:
    """提取块的外层 N 层结构签名（不含文字内容）。"""
    layers: list[tuple[str, ...]] = []

    def walk(el: Tag, depth: int) -> None:
        if depth > _PEEK_LAYERS:
            return
        if not isinstance(el, Tag) or el.name != "section":
            return
        layers.append(_layer_sig(el))
        if depth == 0:
            for c in el.children:
                if isinstance(c, Tag) and c.name == "section":
                    walk(c, depth + 1)

    walk(blk, 0)
    return tuple(layers)


def _get_main_font_size(blk: Tag) -> int:
    """块内主要文字的字号（按文字量加权，取最多的）。"""
    c: Counter[int] = Counter()
    for ns in blk.find_all(string=True):
        t = str(ns).strip()
        if len(t) < 2:
            continue
        p = ns.parent
        while p and getattr(p, "name", None):
            m = re.search(r"font-size\s*:\s*(\d+)px", p.get("style", "") or "")
            if m:
                c[int(m.group(1))] += len(t)
                break
            p = p.parent
    return c.most_common(1)[0][0] if c else 0


def _get_main_color(blk: Tag) -> str:
    """块内主要文字颜色。"""
    c: Counter[str] = Counter()
    for ns in blk.find_all(string=True):
        t = str(ns).strip()
        if len(t) < 2:
            continue
        p = ns.parent
        while p and getattr(p, "name", None):
            m = re.search(r"color\s*:\s*(rgb\([^)]+\)|#[0-9a-fA-F]+)",
                          p.get("style", "") or "")
            if m:
                c[m.group(1)] += len(t)
                break
            p = p.parent
    return c.most_common(1)[0][0] if c else ""


def _has_img(blk: Tag) -> bool:
    return bool(blk.find("img"))


def _guess_is_heading(blks: list[Tag]) -> bool:
    """启发式判断：块文字平均很短（<30字）→ 标题层；较长 → 正文层。"""
    avg_len = sum(len(b.get_text(strip=True)) for b in blks) / len(blks)
    return avg_len < 30


@dataclass
class LevelInfo:
    """模板的一个层级。"""
    level_id: int                    # 1, 2, 3...（按字号从大到小排）
    sig_hash: str                    # 结构签名的 hash（调试用）
    font_size: int                   # 主要字号
    color: str                       # 主要颜色
    is_heading: bool                 # True=独立顶层标题块，False=正文内子层
    block_count: int                 # 模板中该层级的块数
    html_sample: str                 # 一个 HTML 片段样例（M7 克隆用）
    content_samples: list[str]       # 几段文字样例（给 LLM 映射参考）
    signature: tuple = field(default=(), repr=False)  # 完整签名（调试用）

    def to_dict(self) -> dict:
        return {
            "level_id": self.level_id,
            "font_size": self.font_size,
            "color": self.color,
            "is_heading": self.is_heading,
            "block_count": self.block_count,
            "content_samples": self.content_samples,
        }


@dataclass
class TemplateStructure:
    """模板的完整结构信息。"""
    source_file: str
    levels: list[LevelInfo]

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "levels": [lv.to_dict() for lv in self.levels],
        }

    def render_summary(self) -> str:
        """人类/LLM 可读的结构摘要。"""
        lines = [f"模板结构（来源：{self.source_file}）", f"共 {len(self.levels)} 个层级：", ""]
        for lv in self.levels:
            kind = "标题" if lv.is_heading else "正文内子层"
            lines.append(
                f"  层级{lv.level_id} [{lv.font_size}px {lv.color}] {kind}"
                f"（{lv.block_count}个块）"
            )
            for s in lv.content_samples:
                lines.append(f"    · {s[:40]}")
        return "\n".join(lines)


def extract_template(html_path: Path) -> TemplateStructure:
    """解析模板 HTML，提取层级结构。

    1. 找到 <article> 下的根 <section>
    2. 取直接子 <section> 作为顶层块
    3. 按外层签名分组 → 层级
    4. 区分标题层（独立块）vs 正文内子层（块内嵌套的节点）
    """
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    article = soup.find("article") or soup.body
    if not article:
        raise ValueError("HTML 中找不到 <article> 或 <body>")

    root_sec = article.find("section")
    if not root_sec:
        raise ValueError("HTML 中找不到根 <section>")

    blocks = [c for c in root_sec.children if isinstance(c, Tag) and c.name == "section"]
    blocks = [b for b in blocks if b.get_text(strip=True)]

    # 按外层签名分组
    groups: dict[str, list[Tag]] = defaultdict(list)
    for blk in blocks:
        sig = _outer_sig(blk)
        sig_hash = hashlib.md5(str(sig).encode()).hexdigest()[:8]
        groups[sig_hash].append(blk)

    # 按字号从大到小排序
    sorted_groups = sorted(
        groups.items(),
        key=lambda x: _get_main_font_size(x[1][0]),
        reverse=True,
    )

    # 构建 LevelInfo
    levels: list[LevelInfo] = []
    for i, (sig_hash, blks) in enumerate(sorted_groups):
        fs = _get_main_font_size(blks[0])
        color = _get_main_color(blks[0])
        content_samples = []
        seen = set()
        for b in blks:
            t = b.get_text(strip=True)
            key = t[:20]
            if key not in seen and len(content_samples) < _MAX_CONTENT_SAMPLES:
                seen.add(key)
                content_samples.append(t)

        levels.append(LevelInfo(
            level_id=i + 1,
            sig_hash=sig_hash,
            font_size=fs,
            color=color,
            is_heading=_guess_is_heading(blks),
            block_count=len(blks),
            html_sample=str(blks[0]),
            content_samples=content_samples,
            signature=_outer_sig(blks[0]),
        ))

    return TemplateStructure(
        source_file=html_path.name,
        levels=levels,
    )
