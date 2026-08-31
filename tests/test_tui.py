"""TUI 测试：放文件 → y → 自动处理 → 交付。"""

from __future__ import annotations

import contextlib
import io
import sys

from xiumi_layout_agent.chat.llm import MockLLM


def _run(inputs: str, tmp_path, replies=None) -> str:
    from xiumi_layout_agent.chat.tui import run_tui

    inbox = tmp_path / "inbox"
    inbox.mkdir(exist_ok=True)
    llm = MockLLM(replies=replies or [])
    llm.on_message(lambda msgs: '[{"index": 1, "level": 1}]')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        old = sys.stdin
        sys.stdin = io.StringIO(inputs)
        try:
            run_tui(llm=llm, inbox=inbox)
        finally:
            sys.stdin = old
    return buf.getvalue()


def test_opening_message(tmp_path):
    out = _run("退出\n", tmp_path)
    assert "模板HTML" in out
    assert ".md" in out
    assert "y" in out


def test_quit(tmp_path):
    out = _run("退出\n", tmp_path)
    assert "再见" in out


def test_no_files(tmp_path):
    out = _run("y\n退出\n", tmp_path)
    assert "没找到 HTML" in out


def test_only_html(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "tmpl.html").write_text(
        "<html><body><article><section>"
        "<section style='font-size:24px;color:#fff'><p>标题</p></section>"
        "</section></article></body></html>", encoding="utf-8")
    llm = MockLLM()
    llm.on_message(lambda m: "[]")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        old = sys.stdin
        sys.stdin = io.StringIO("y\n退出\n")
        try:
            from xiumi_layout_agent.chat.tui import run_tui
            run_tui(llm=llm, inbox=inbox)
        finally:
            sys.stdin = old
    assert "没找到文字稿" in buf.getvalue()


def test_n_means_not_yet(tmp_path):
    out = _run("n\n退出\n", tmp_path)
    assert "不着急" in out


def test_garbage_files_cleaned(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / ".DS_Store").write_text("junk")
    (inbox / "x.html:Zone.Identifier").write_text("junk")
    out = _run("y\n退出\n", tmp_path)
    assert "没找到 HTML" in out  # 垃圾被清了，没真文件
