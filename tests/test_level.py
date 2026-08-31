"""normalize/level.py 测试：LLM 驱动的新稿大纲映射（mock LLM）。"""

from __future__ import annotations

import pytest

from xiumi_layout_agent.chat.llm import MockLLM
from xiumi_layout_agent.normalize.level import _build_prompt, _guess_level, _parse_json, level_draft
from xiumi_layout_agent.normalize.outline import Block
from xiumi_layout_agent.template.extract import LevelInfo, TemplateStructure


def _fake_template() -> TemplateStructure:
    return TemplateStructure(
        source_file="test.html",
        levels=[
            LevelInfo(
                level_id=1, sig_hash="a", font_size=16, color="rgb(30,46,82)",
                is_heading=True, block_count=1, html_sample="<section>h1</section>",
                content_samples=["四、左右翼民粹主义"],
            ),
            LevelInfo(
                level_id=2, sig_hash="b", font_size=14, color="rgb(62,62,62)",
                is_heading=True, block_count=5, html_sample="<section>h2</section>",
                content_samples=["摘要", "一、资本主义危机", "导语"],
            ),
            LevelInfo(
                level_id=3, sig_hash="c", font_size=14, color="rgb(25,43,78)",
                is_heading=False, block_count=1, html_sample="<section>body</section>",
                content_samples=["民粹主义作为一种反建制的..."],
            ),
        ],
    )


def test_build_prompt_contains_template_info():
    tpl = _fake_template()
    prompt = _build_prompt("  1. [标题#] test", 1, tpl)
    assert "层级1" in prompt
    assert "层级3" in prompt
    assert "16px" in prompt


def test_build_prompt_contains_outline():
    tpl = _fake_template()
    outline = "  1. [标题#] 大标题\n  2. [正文] 首句…尾句"
    prompt = _build_prompt(outline, 2, tpl)
    assert "大标题" in prompt
    assert "首句" in prompt


def test_parse_json_direct():
    reply = '[{"index": 1, "level": 1}, {"index": 2, "level": 3}]'
    result = _parse_json(reply)
    assert len(result) == 2
    assert result[0]["index"] == 1


def test_parse_json_in_code_block():
    reply = '```json\n[{"index": 1, "level": 2}]\n```'
    result = _parse_json(reply)
    assert len(result) == 1


def test_parse_json_invalid_raises():
    with pytest.raises(ValueError):
        _parse_json("not json")


def test_level_draft_with_mock_llm():
    tpl = _fake_template()
    md = "# 迈向知识自主\n\n## 摘要\n\n这是正文。很长的正文。最后一句。\n\n## 导语"
    mock_reply = '[{"index": 1, "level": 1}, {"index": 2, "level": 2}, {"index": 3, "level": 3}, {"index": 4, "level": 2}]'
    llm = MockLLM(replies=[mock_reply])
    result = level_draft(md, tpl, llm)

    assert len(result) == 4
    assert result[0] == {"level": 1, "text": "迈向知识自主"}
    assert result[1] == {"level": 2, "text": "摘要"}
    assert result[2]["level"] == 3
    assert "这是正文" in result[2]["text"]
    assert result[3] == {"level": 2, "text": "导语"}


def test_level_draft_fallback_for_missing_assignments():
    """LLM 漏标某些块时，用兜底逻辑补上。"""
    tpl = _fake_template()
    md = "# 标题\n\n正文段落。"
    mock_reply = '[{"index": 1, "level": 1}]'  # 漏了 index 2
    llm = MockLLM(replies=[mock_reply])
    result = level_draft(md, tpl, llm)
    assert len(result) == 2
    assert result[0]["level"] == 1
    assert result[1]["level"] == 3  # 兜底：正文 → 最大的正文层级


def test_guess_level_heading():
    tpl = _fake_template()
    blk = Block(index=1, kind="heading", md_level=1, preview="x", text="x")
    assert _guess_level(blk, tpl) == 1  # 最大的标题层级


def test_guess_level_body():
    tpl = _fake_template()
    blk = Block(index=1, kind="body", md_level=None, preview="x", text="x")
    assert _guess_level(blk, tpl) == 3  # 最大的正文层级


def test_level_draft_llm_called_once():
    tpl = _fake_template()
    llm = MockLLM(replies=["[]"])
    level_draft("# test", tpl, llm)
    assert len(llm.calls) == 1
    assert "JSON" in llm.calls[0][0]["content"]
