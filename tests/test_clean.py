"""normalize/clean.py 测试：文字稿清洗。"""

from xiumi_layout_agent.normalize.clean import clean_text


def test_crlf_normalized():
    assert clean_text("line1\r\nline2\rline3") == "line1\nline2\nline3"


def test_fullwidth_space():
    assert clean_text("一\u3000二\u3000三") == "一 二 三"


def test_zerowidth_removed():
    assert clean_text("abc\u200bdef\ufeffghi") == "abcdefghi"


def test_trailing_whitespace():
    assert clean_text("line1   \nline2\t\n") == "line1\nline2"


def test_multiblank_compressed():
    raw = "a\n\n\n\n\n\nb"
    result = clean_text(raw)
    assert "\n\n\n\n" not in result
    assert "a" in result and "b" in result


def test_strip():
    assert clean_text("  \n hello \n  ") == "hello"


def test_preserve_normal_text():
    raw = "一、标题\n\n正文段落\n\n二、标题"
    assert clean_text(raw) == raw


def test_combined_dirty():
    raw = "\r\n\u3000一、标题\u3000\r\n\r\n\r\n\r\n正文\u200b内容   \r\n"
    result = clean_text(raw)
    assert "\r" not in result
    assert "\u3000" not in result
    assert "\u200b" not in result
    assert "一、标题" in result
    assert "正文内容" in result
