"""材料检查：扫描 workspace/<task_id>/input/ 各目录，报告缺件/错位。

归档结构（由 guide.py + tui._archive 产生）：
    input/template/   模板文字稿 + 模板网页文件
    input/draft/      新文字稿
    input/images/     图片（可选）

引导阶段按"先来后到"对号入座、不看文件类型，因此可能错位：
本模块靠内容特征（HTML 标签 / 图片魔数 / 纯文本）纠正或标记疑点，
拿不准时不擅自搬文件，而是在报告里标"疑似错位"请客户确认。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# 判断类型用的特征
_HTML_TAGS = (b"<html", b"<head", b"<body", b"<div", b"<section",
              b"<span", b"<!doctype", b"<table", b"<img", b"<p>", b"<p ")
_IMG_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")
_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_HTML_EXT = {".html", ".htm", ".xhtml"}
_PEEK = 4096  # 只读前 4KB 判断类型，避免大文件全读

_KIND_CN = {"html": "网页", "text": "文本", "image": "图片", "unknown": "未知"}


def classify(path: Path) -> str:
    """按内容特征判断文件类型：html / text / image / unknown。

    优先看内容（HTML 标签、图片魔数），内容不明时用扩展名兜底。
    """
    head = b""
    try:
        with path.open("rb") as fh:
            head = fh.read(_PEEK)
    except OSError:
        return "unknown"

    low = head.lower()
    if any(t in low for t in (t.lower() for t in _HTML_TAGS)):
        return "html"
    if any(head.startswith(m) for m in _IMG_MAGIC):
        return "image"
    if head[:4] == b"RIFF" and b"WEBP" in head[:16]:
        return "image"

    ext = path.suffix.lower()
    if ext in _HTML_EXT:
        return "html"
    if ext in _IMG_EXT:
        return "image"
    if not head:
        return "unknown"
    # 能当文本解码就算文本（编辑部文字稿多为 utf-8，少数老文档 gbk）
    for enc in ("utf-8", "gbk"):
        try:
            head.decode(enc)
            return "text"
        except UnicodeDecodeError:
            continue
    return "unknown"


def _preview(path: Path, kind: str) -> str:
    """取内容摘要：文本取前若干字，网页取开头，图片不取内容。"""
    if kind == "image":
        return ""
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")[:200]
    except OSError:
        return ""
    return " ".join(raw.split())[:60]


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n / 1024 / 1024:.1f}MB"


@dataclass
class FileInfo:
    name: str
    kind: str
    size: int
    preview: str


@dataclass
class ScanResult:
    task_id: str
    dirs: dict[str, list[FileInfo]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if not self.problems:
            return "齐全"
        if any("疑似错位" in p for p in self.problems):
            return "疑似错位"
        return "缺件"

    def render(self) -> str:
        labels = {
            "template": "template/（应有：模板文字稿 + 模板网页文件）",
            "draft": "draft/（应有：新文字稿）",
            "images": "images/（图片，可选）",
        }
        lines = [f"材料检查结果（任务号 {self.task_id}）：", ""]
        for d in ("template", "draft", "images"):
            files = self.dirs.get(d, [])
            lines.append(labels[d])
            if not files:
                lines.append("  （无文件）")
            for f in files:
                head = f"  - {f.name}  {_KIND_CN.get(f.kind, '?')}  {_human_size(f.size)}"
                if f.preview:
                    head += f'  "{f.preview}"'
                lines.append(head)
            lines.append("")
        if not self.problems:
            lines.append("判断：材料齐全。")
        else:
            tag = "疑似错位，需跟客户确认。" if self.verdict == "疑似错位" else "缺件，需补材料。"
            lines.append(f"判断：{tag}")
            lines.append("问题：")
            for i, p in enumerate(self.problems, 1):
                lines.append(f"{i}. {p}")
        return "\n".join(lines)


def scan_input(base: Path, task_id: str) -> ScanResult:
    """扫描 input/ 根目录，返回检查结果。base 即 workspace/<task_id>/input/。"""
    res = ScanResult(task_id=task_id)
    for d in ("template", "draft", "images"):
        files: list[FileInfo] = []
        ddir = base / d
        if ddir.exists():
            for p in sorted(ddir.iterdir(), key=lambda x: x.name):
                if not p.is_file():
                    continue
                kind = classify(p)
                files.append(FileInfo(
                    name=p.name, kind=kind, size=p.stat().st_size,
                    preview=_preview(p, kind),
                ))
        res.dirs[d] = files
    _detect(res)
    return res


def _detect(res: ScanResult) -> None:
    """根据各目录文件类型分布，找出缺件与疑似错位。

    错位能解释的"缺件"不重复上报（如模板网页文件跑到 draft/，就报错位而非缺件）。
    """
    tpl = res.dirs["template"]
    draft = res.dirs["draft"]
    imgs = res.dirs["images"]

    tpl_html = [f for f in tpl if f.kind == "html"]
    tpl_text = [f for f in tpl if f.kind == "text"]
    draft_text = [f for f in draft if f.kind == "text"]
    draft_html = [f for f in draft if f.kind == "html"]

    # ---- 错位：图片/网页文件出现在不该出现的目录 ----
    for f in tpl:
        if f.kind == "image":
            res.problems.append(f"疑似错位：template/{f.name} 是图片，应在 images/。")
    for f in draft:
        if f.kind == "image":
            res.problems.append(f"疑似错位：draft/{f.name} 是图片，应在 images/。")
    for f in draft_html:
        res.problems.append(f"疑似错位：draft/{f.name} 是网页文件，应在 template/。")
    for f in imgs:
        if f.kind in ("html", "text"):
            res.problems.append(
                f"疑似错位：images/{f.name} 是{_KIND_CN[f.kind]}，应在 template/ 或 draft/。"
            )

    # ---- 错位：新文字稿被收进 template/（引导先来后到的已知缺陷）----
    # template/ 文本偏多而 draft/ 没文本 → 其中一个文本很可能是新文字稿
    draft_in_tpl = len(tpl_text) >= 2 and not draft_text
    if draft_in_tpl:
        names = "、".join(f.name for f in tpl_text)
        res.problems.append(
            f"疑似错位：template/ 有 {len(tpl_text)} 个文本文件（{names}），"
            "而 draft/ 没有新文字稿，可能其中一个是新文字稿被错放进了 template/。"
        )

    # ---- 缺件（被错位解释的不重复报缺）----
    if not tpl_html and not draft_html:
        res.problems.append("template/ 缺模板网页文件。")
    if not tpl_text:
        res.problems.append("template/ 缺模板文字稿。")
    if not draft_text and not draft_in_tpl:
        res.problems.append("draft/ 缺新文字稿。")
