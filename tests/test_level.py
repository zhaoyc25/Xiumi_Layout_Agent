"""normalize/level.py 测试：LLM 驱动的新稿分块+分级+映射（mock LLM）。"""

from __future__ import annotations

import pytest

from xiumi_layout_agent.chat.llm import MockLLM
from xiumi_layout_agent.normalize.level import _build_prompt, _parse_json, level_draft
from xiumi_layout_agent.template.extract import LevelInfo, TemplateStructure


def _fake_template() -> TemplateStructure:
    return TemplateStructure(
        source_file="test.html",
        levels=[
            LevelInfo(
                level_id=1, sig_hash="a", font_size=24, color="rgb(255,255,255)",
                is_heading=True, block_count=3, html_sample="<section>h1</section>",
                content_samples=["一、文娱活动", "中关村篇", "新生报到"],
            ),
            LevelInfo(
                level_id=2, sig_hash="b", font_size=20, color="rgb(255,255,255)",
                is_heading=True, block_count=11, html_sample="<section>h2</section>",
                content_samples=["1.「初见·惊喜款」新生晚会", "3.住", "4.行"],
            ),
            LevelInfo(
                level_id=3, sig_hash="c", font_size=14, color="rgb(255,255,255)",
                is_heading=False, block_count=13, html_sample="<section>body</section>",
                content_samples=["从舞培、路演到联谊破冰...", "桂香渐起，明月将圆..."],
            ),
            LevelInfo(
                level_id=4, sig_hash="d", font_size=12, color="rgb(62,62,62)",
                is_heading=True, block_count=1, html_sample="<section>footer</section>",
                content_samples=["文案 | 研究生会"],
            ),
        ],
    )


def test_build_prompt_contains_template_info():
    tpl = _fake_template()
    prompt = _build_prompt("1: test", 1, tpl)
    assert "层级1" in prompt
    assert "层级4" in prompt
    assert "24px" in prompt
    assert "12px" in prompt


def test_build_prompt_contains_line_count():
    tpl = _fake_template()
    prompt = _build_prompt("1: a\n2: b", 2, tpl)
    assert "共2行" in prompt


def test_build_prompt_asks_for_from_to_line():
    tpl = _fake_template()
    prompt = _build_prompt("1: test", 1, tpl)
    assert "from_line" in prompt
    assert "to_line" in prompt


def test_parse_json_direct():
    reply = '[{"level": 1, "from_line": 1, "to_line": 3}, {"level": 3, "from_line": 4, "to_line": 10}]'
    result = _parse_json(reply)
    assert len(result) == 2
    assert result[0]["level"] == 1
    assert result[1]["from_line"] == 4


def test_parse_json_in_code_block():
    reply = '好的\n```json\n[{"level": 1, "from_line": 1, "to_line": 1}]\n```\n完毕'
    result = _parse_json(reply)
    assert len(result) == 1


def test_parse_json_with_surrounding_text():
    reply = '分析完毕。\n[{"level": 2, "from_line": 1, "to_line": 5}]\n以上结果。'
    result = _parse_json(reply)
    assert len(result) == 1


def test_parse_json_invalid_raises():
    with pytest.raises(ValueError):
        _parse_json("这不是JSON")


def test_level_draft_extracts_text_by_line_numbers():
    """LLM 返回行号，level_draft 按行号切出原文。"""
    tpl = _fake_template()
    text = "一、标题\n\n正文第一段\n正文第二段\n\n文案 | 编辑部"
    # 行号：1=一、标题, 2=空, 3=正文第一段, 4=正文第二段, 5=空, 6=文案
    mock_reply = '[{"level": 1, "from_line": 1, "to_line": 1}, {"level": 3, "from_line": 3, "to_line": 4}, {"level": 4, "from_line": 6, "to_line": 6}]'
    llm = MockLLM(replies=[mock_reply])
    result = level_draft(text, tpl, llm)

    assert len(result) == 3
    assert result[0] == {"level": 1, "text": "一、标题"}
    assert result[1] == {"level": 3, "text": "正文第一段\n正文第二段"}
    assert result[2] == {"level": 4, "text": "文案 | 编辑部"}


def test_level_draft_clamps_line_numbers():
    """行号越界时自动夹到合法范围。"""
    tpl = _fake_template()
    text = "只有一行"
    mock_reply = '[{"level": 1, "from_line": 0, "to_line": 99}]'
    llm = MockLLM(replies=[mock_reply])
    result = level_draft(text, tpl, llm)
    assert len(result) == 1
    assert result[0]["text"] == "只有一行"


def test_level_draft_skips_empty_blocks():
    """from_line == to_line 时空块跳过。"""
    tpl = _fake_template()
    text = "内容"
    mock_reply = '[{"level": 1, "from_line": 1, "to_line": 1}, {"level": 2, "from_line": 2, "to_line": 2}]'
    llm = MockLLM(replies=[mock_reply])
    result = level_draft(text, tpl, llm)
    assert len(result) == 1
    assert result[0]["text"] == "内容"


def test_level_draft_llm_called_once():
    tpl = _fake_template()
    llm = MockLLM(replies=["[]"])
    level_draft("test", tpl, llm)
    assert len(llm.calls) == 1
    assert llm.calls[0][0]["role"] == "system"
    assert "JSON" in llm.calls[0][0]["content"]
