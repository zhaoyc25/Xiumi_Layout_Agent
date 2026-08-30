"""scan_inbox 材料检查测试：齐全 / 缺件 / 错位 三类用例。"""

from __future__ import annotations

from pathlib import Path

from xiumi_layout_agent.chat.scan import classify, scan_input
from xiumi_layout_agent.chat.tools import Session, build_default_registry

HTML = "<!DOCTYPE html><html><head><title>t</title></head><body><p>模板正文</p></body></html>"
TEXT = "国关融媒体编辑部\n关于举办某某会议的通知\n一、时间\n二、地点"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def _build_input(root: Path, task_id: str, files: dict) -> Path:
    """在 root/workspace/<task_id>/input/<dir>/ 下建文件。files: {dir: [(name, content)]}。"""
    base = root / "workspace" / task_id / "input"
    for d, items in files.items():
        ddir = base / d
        ddir.mkdir(parents=True, exist_ok=True)
        for name, content in items:
            p = ddir / name
            if isinstance(content, bytes):
                p.write_bytes(content)
            else:
                p.write_text(content, encoding="utf-8")
    return base


# ---- classify ----

def test_classify_html(tmp_path):
    p = tmp_path / "a.html"
    p.write_text(HTML, encoding="utf-8")
    assert classify(p) == "html"


def test_classify_html_by_content_not_ext(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text(HTML, encoding="utf-8")
    assert classify(p) == "html"


def test_classify_image_png(tmp_path):
    p = tmp_path / "a.png"
    p.write_bytes(PNG)
    assert classify(p) == "image"


def test_classify_image_jpg(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_bytes(JPG)
    assert classify(p) == "image"


def test_classify_text(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text(TEXT, encoding="utf-8")
    assert classify(p) == "text"


# ---- 齐全 ----

def test_scan_complete(tmp_path):
    base = _build_input(tmp_path, "t1", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML)],
        "draft": [("新稿.txt", "新文字稿内容")],
        "images": [("图1.png", PNG)],
    })
    res = scan_input(base, "t1")
    assert res.verdict == "齐全"
    assert res.problems == []
    assert "齐全" in res.render()


def test_scan_complete_no_images(tmp_path):
    base = _build_input(tmp_path, "t2", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML)],
        "draft": [("新稿.txt", "新文字稿")],
    })
    res = scan_input(base, "t2")
    assert res.verdict == "齐全"


# ---- 缺件 ----

def test_scan_missing_html(tmp_path):
    base = _build_input(tmp_path, "t3", {
        "template": [("模板稿.txt", TEXT)],
        "draft": [("新稿.txt", "新文字稿")],
    })
    res = scan_input(base, "t3")
    assert res.verdict == "缺件"
    assert any("缺模板网页文件" in p for p in res.problems)


def test_scan_missing_draft(tmp_path):
    base = _build_input(tmp_path, "t4", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML)],
        "draft": [],
    })
    res = scan_input(base, "t4")
    assert res.verdict == "缺件"
    assert any("缺新文字稿" in p for p in res.problems)


def test_scan_missing_template_text(tmp_path):
    base = _build_input(tmp_path, "t5", {
        "template": [("模板.html", HTML)],
        "draft": [("新稿.txt", "新文字稿"), ("另一.txt", "x")],
    })
    res = scan_input(base, "t5")
    # template 缺文字稿（只有网页文件）；draft 有文本不报缺新稿，直接报缺模板文字稿
    assert res.verdict == "缺件"
    assert any("缺模板文字稿" in p for p in res.problems)


# ---- 错位 ----

def test_scan_misplaced_draft_into_template(tmp_path):
    """新文字稿被收进 template/：template 有2个文本，draft 空。"""
    base = _build_input(tmp_path, "t6", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML), ("新稿.txt", "新文字稿")],
        "draft": [],
    })
    res = scan_input(base, "t6")
    assert res.verdict == "疑似错位"
    assert any("新文字稿被错放进了 template" in p for p in res.problems)
    # 不应重复报"缺新文字稿"（已被错位解释）
    assert not any("缺新文字稿" in p for p in res.problems)


def test_scan_misplaced_text_in_images(tmp_path):
    """非图片文件被收进 images/。"""
    base = _build_input(tmp_path, "t7", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML)],
        "draft": [("新稿.txt", "新文字稿")],
        "images": [("误放.txt", "文本内容")],
    })
    res = scan_input(base, "t7")
    assert res.verdict == "疑似错位"
    assert any("images/误放.txt 是文本" in p for p in res.problems)


def test_scan_misplaced_html_into_draft(tmp_path):
    """模板网页文件被收进 draft/。"""
    base = _build_input(tmp_path, "t8", {
        "template": [("模板稿.txt", TEXT)],
        "draft": [("模板.html", HTML)],
    })
    res = scan_input(base, "t8")
    assert res.verdict == "疑似错位"
    assert any("网页文件，应在 template" in p for p in res.problems)
    # 网页文件虽错位但仍在，不报"缺模板网页文件"
    assert not any("缺模板网页文件" in p for p in res.problems)


def test_scan_misplaced_image_in_template(tmp_path):
    base = _build_input(tmp_path, "t9", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML), ("图.png", PNG)],
        "draft": [("新稿.txt", "新文字稿")],
    })
    res = scan_input(base, "t9")
    assert res.verdict == "疑似错位"
    assert any("template/图.png 是图片" in p for p in res.problems)


def test_scan_render_format(tmp_path):
    base = _build_input(tmp_path, "t10", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML)],
        "draft": [("新稿.txt", "新文字稿")],
    })
    out = scan_input(base, "t10").render()
    assert "template/" in out
    assert "draft/" in out
    assert "images/" in out
    assert "判断：材料齐全。" in out


# ---- 工具注册表接线 ----

def test_scan_inbox_tool_via_registry(tmp_path, monkeypatch):
    from xiumi_layout_agent.chat import config as cfg
    monkeypatch.setattr(cfg, "_REPO_ROOT", tmp_path)

    _build_input(tmp_path, "20260831_demo", {
        "template": [("模板稿.txt", TEXT), ("模板.html", HTML)],
        "draft": [("新稿.txt", "新文字稿")],
    })
    s = Session()
    s.data["task_id"] = "20260831_demo"
    reg = build_default_registry(s)
    out = reg.get("scan_inbox").run({})
    assert "齐全" in out
    assert "20260831_demo" in out


def test_scan_inbox_tool_missing_task_id():
    s = Session()
    reg = build_default_registry(s)
    out = reg.get("scan_inbox").run({})
    assert "任务号" in out


def test_scan_inbox_tool_dir_not_found(tmp_path, monkeypatch):
    from xiumi_layout_agent.chat import config as cfg
    monkeypatch.setattr(cfg, "_REPO_ROOT", tmp_path)
    s = Session()
    s.data["task_id"] = "no_such"
    reg = build_default_registry(s)
    out = reg.get("scan_inbox").run({})
    assert "没找到" in out
