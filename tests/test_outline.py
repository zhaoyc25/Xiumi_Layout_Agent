"""normalize/outline.py 测试：Markdown 大纲解析。"""

from xiumi_layout_agent.normalize.outline import _preview_body, parse_markdown, render_outline


def test_parse_headings():
    md = "# 大标题\n\n## 二级标题\n\n### 三级标题"
    blocks = parse_markdown(md)
    assert len(blocks) == 3
    assert blocks[0].kind == "heading" and blocks[0].md_level == 1
    assert blocks[1].md_level == 2
    assert blocks[2].md_level == 3


def test_parse_body_paragraph():
    md = "# 标题\n\n这是正文段落。第二句话。最后一句。"
    blocks = parse_markdown(md)
    assert len(blocks) == 2
    assert blocks[1].kind == "body"
    assert blocks[1].md_level is None
    assert "这是正文段落" in blocks[1].text


def test_parse_skip_hr_and_blank():
    md = "# 标题\n\n---\n\n正文\n\n---\n\n## 二"
    blocks = parse_markdown(md)
    assert len(blocks) == 3  # 标题、正文、二
    assert blocks[0].text == "标题"
    assert blocks[1].text == "正文"
    assert blocks[2].text == "二"


def test_parse_multi_line_body():
    md = "# 标题\n\n第一行\n第二行\n第三行"
    blocks = parse_markdown(md)
    assert len(blocks) == 2
    assert "第一行" in blocks[1].text
    assert "第三行" in blocks[1].text


def test_preview_body_short():
    text = "只有五个字"
    assert _preview_body(text) == "只有五个字"


def test_preview_body_long():
    text = "这是一段很长的正文，超过十个字的内容不应该出现在预览里。"
    assert _preview_body(text) == "这是一段很长的正文，"  # 前10字含标点


def test_preview_body_exact_ten():
    text = "一二三四五六七八九十"
    assert _preview_body(text) == "一二三四五六七八九十"


def test_render_outline():
    md = "# 标题\n\n正文一。正文二。"
    blocks = parse_markdown(md)
    outline = render_outline(blocks)
    assert "1." in outline
    assert "标题" in outline
    assert "2." in outline
    assert "正文" in outline


def test_index_sequential():
    md = "# A\n\nB\n\n## C\n\nD"
    blocks = parse_markdown(md)
    assert [b.index for b in blocks] == [1, 2, 3, 4]
