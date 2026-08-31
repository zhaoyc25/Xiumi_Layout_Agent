"""replace/core.py 测试：克隆模板节点+替换文字+清理图片+拼装。"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from xiumi_layout_agent.replace.core import (
    _clean_images,
    _is_plain_body,
    _replace_text,
    replace_template,
)
from xiumi_layout_agent.template.extract import LevelInfo, TemplateStructure

# 迷你 xiumi 风格 HTML：3 个层级
_SAMPLE_HTML = """<!DOCTYPE html>
<html><body>
<article>
<section>
  <section style="display: flex; text-align: center; box-sizing: border-box;">
    <section style="display: inline-block; background-color: rgb(145,184,186); border-radius: 0px 26px; padding: 5px 15px; box-sizing: border-box;">
      <section style="font-size: 24px; color: rgb(255,255,255); box-sizing: border-box;">
        <p><b>原标题</b></p>
      </section>
    </section>
  </section>
  <p></p>
  <section style="text-align: left; box-sizing: border-box;">
    <section style="font-size: 20px; color: rgb(255,255,255); box-sizing: border-box;">
      <p>原二级标题</p>
    </section>
  </section>
  <p></p>
  <section style="display: flex; text-align: center; box-sizing: border-box;">
    <section style="display: inline-block; width: 87%; background-color: rgb(255,255,255); padding: 15px 26px; box-sizing: border-box;">
      <section style="text-align: justify; box-sizing: border-box;">
        <p>原正文段落，这是一段比较长的正文内容用于测试正文层级的替换效果。</p>
      </section>
      <section style="box-sizing: border-box;">
        <section style="display: inline-block; width: 100%; box-sizing: border-box;">
          <img src="old.png" />
        </section>
      </section>
    </section>
  </section>
</section>
</article>
</body></html>"""


def _write_sample(tmp_path: Path) -> Path:
    p = tmp_path / "sample.html"
    p.write_text(_SAMPLE_HTML, encoding="utf-8")
    return p


def _fake_template() -> TemplateStructure:
    return TemplateStructure(
        source_file="sample.html",
        levels=[
            LevelInfo(
                level_id=1, sig_hash="a", font_size=24, color="rgb(255,255,255)",
                is_heading=True, block_count=1,
                html_sample='<section style="display: flex; text-align: center; box-sizing: border-box;"><section style="display: inline-block; background-color: rgb(145,184,186); border-radius: 0px 26px; padding: 5px 15px; box-sizing: border-box;"><section style="font-size: 24px; color: rgb(255,255,255); box-sizing: border-box;"><p><b>原标题</b></p></section></section></section>',
                content_samples=["原标题"],
            ),
            LevelInfo(
                level_id=2, sig_hash="b", font_size=20, color="rgb(255,255,255)",
                is_heading=True, block_count=1,
                html_sample='<section style="text-align: left; box-sizing: border-box;"><section style="font-size: 20px; color: rgb(255,255,255); box-sizing: border-box;"><p>原二级标题</p></section></section>',
                content_samples=["原二级标题"],
            ),
            LevelInfo(
                level_id=3, sig_hash="c", font_size=14, color="rgb(255,255,255)",
                is_heading=False, block_count=1,
                html_sample='<section style="display: flex; text-align: center; box-sizing: border-box;"><section style="display: inline-block; width: 87%; background-color: rgb(255,255,255); padding: 15px 26px; box-sizing: border-box;"><section style="text-align: justify; box-sizing: border-box;"><p>原正文段落，这是一段比较长的正文内容用于测试正文层级的替换效果。</p></section><section style="box-sizing: border-box;"><section style="display: inline-block; width: 100%; box-sizing: border-box;"><img src="old.png" /></section></section></section></section>',
                content_samples=["原正文段落..."],
            ),
        ],
    )


def test_replace_text_basic():
    """克隆块后替换文字，结构不变只改文字。"""
    clone = BeautifulSoup('<section><p><b>原文</b></p></section>', "lxml").find("section")
    _replace_text(clone, "新文字")
    assert clone.get_text(strip=True) == "新文字"
    assert clone.find("b") is not None  # <b> 标签保留


def test_replace_text_bold():
    """**加粗** 转成 <b> 标签。"""
    clone = BeautifulSoup('<section><p>原文</p></section>', "lxml").find("section")
    _replace_text(clone, "**加粗内容**普通内容")
    b = clone.find("b")
    assert b is not None
    assert b.get_text() == "加粗内容"
    assert "普通内容" in clone.get_text()


def test_replace_text_line_break():
    """多行文字的 \\n 转成 <br>。"""
    clone = BeautifulSoup('<section><p>原文</p></section>', "lxml").find("section")
    _replace_text(clone, "第一行\n第二行")
    br = clone.find("br")
    assert br is not None
    assert "第一行" in clone.get_text()
    assert "第二行" in clone.get_text()


def test_replace_text_multi_nodes():
    """多个文字节点：第一个替换，其余删除。"""
    clone = BeautifulSoup('<section>甲<p>乙</p>丙</section>', "lxml").find("section")
    _replace_text(clone, "新文字")
    assert clone.get_text(strip=True) == "新文字"


def test_clean_images_removes_img():
    """正文块内的图片被删除。"""
    clone = BeautifulSoup(
        '<section><section><p>文字</p></section><section><section><img src="x.png"/></section></section></section>',
        "lxml",
    ).find("section")
    assert clone.find("img") is not None
    _clean_images(clone)
    assert clone.find("img") is None
    assert "文字" in clone.get_text()  # 文字保留


def test_replace_template_generates_html(tmp_path):
    """端到端：模板+分级 → result.html。"""
    html_path = _write_sample(tmp_path)
    tpl = _fake_template()
    draft = [
        {"level": 1, "text": "新大标题"},
        {"level": 2, "text": "新二级标题"},
        {"level": 3, "text": "新正文段落内容。"},
        {"level": 2, "text": "第二个二级标题"},
        {"level": 3, "text": "第二段正文。"},
    ]
    result = replace_template(html_path, tpl, draft)

    soup = BeautifulSoup(result, "lxml")
    article = soup.find("article")
    blocks = [c for c in article.find("section").children if hasattr(c, "name") and c.name == "section"]

    assert len(blocks) == 5  # 5 个块
    assert "新大标题" in result
    assert "新二级标题" in result
    assert "新正文段落内容" in result
    assert "第二个二级标题" in result
    assert "第二段正文" in result
    assert "原标题" not in result
    assert "old.png" not in result  # 图片已清理


def test_replace_template_preserves_page_structure(tmp_path):
    """页面结构（article, body, html）保留。"""
    html_path = _write_sample(tmp_path)
    tpl = _fake_template()
    draft = [{"level": 1, "text": "测试"}]
    result = replace_template(html_path, tpl, draft)
    soup = BeautifulSoup(result, "lxml")
    assert soup.find("article") is not None
    assert soup.find("body") is not None


def test_replace_template_skips_missing_level(tmp_path):
    """层级号不存在时跳过该块。"""
    html_path = _write_sample(tmp_path)
    tpl = _fake_template()
    draft = [{"level": 99, "text": "不存在的层级"}, {"level": 1, "text": "正常块"}]
    result = replace_template(html_path, tpl, draft)
    assert "不存在的层级" not in result
    assert "正常块" in result


def test_replace_template_empty_draft(tmp_path):
    """空分级 → 只有页面骨架。"""
    html_path = _write_sample(tmp_path)
    tpl = _fake_template()
    result = replace_template(html_path, tpl, [])
    soup = BeautifulSoup(result, "lxml")
    assert soup.find("article") is not None


def test_replace_text_multiline_indent():
    """多段文字：第二段起段首缩进（全角空格），<br> 分隔。"""
    clone = BeautifulSoup('<section><p>原文</p></section>', "lxml").find("section")
    _replace_text(clone, "第一段\n第二段\n第三段")
    s = str(clone)
    assert "第一段" in s
    assert "第二段" in s
    assert "第三段" in s
    assert "　　第二段" in s  # 第二段缩进
    assert "　　第三段" in s
    assert clone.find("br") is not None


def test_replace_text_drops_empty_shells():
    """模板多 <p> 占位：替换后不留空 <p>（消除莫名空行）。"""
    clone = BeautifulSoup(
        '<section><section><p>段1</p><p>段2</p><p>段3</p></section></section>', "lxml"
    ).find("section")
    _replace_text(clone, "新文字")
    ps = clone.find_all("p")
    assert len(ps) == 1  # 只剩一个 <p>，其余空壳被删
    assert ps[0].get_text(strip=True) == "新文字"


def test_replace_template_merges_adjacent_body(tmp_path):
    """相邻同 level 的普通正文块合并进一个文本框，段落缩进。"""
    html_path = _write_sample(tmp_path)
    tpl = _fake_template()
    draft = [
        {"level": 3, "text": "段落一。"},
        {"level": 3, "text": "段落二。"},
        {"level": 2, "text": "中间标题"},
        {"level": 3, "text": "段落三。"},
    ]
    result = replace_template(html_path, tpl, draft)
    soup = BeautifulSoup(result, "lxml")
    blocks = [c for c in soup.find("article").find("section").children
              if hasattr(c, "name") and c.name == "section"]
    assert len(blocks) == 3  # 段落一二合并 → 1块；中间标题 → 1块；段落三 → 1块
    assert "段落一" in result and "段落二" in result
    assert "　　段落二" in result  # 第二段缩进
    assert "段落三" in result


def test_replace_template_keeps_special_level_separate(tmp_path):
    """带边框的特殊层级（摘要/关键字等）即使相邻也不合并，各自独立成框。"""
    tpl = TemplateStructure(
        source_file="x.html",
        levels=[LevelInfo(
            level_id=1, sig_hash="a", font_size=14, color="rgb(0,0,0)",
            is_heading=False, block_count=1,
            html_sample='<section style="border: 2px solid red; padding: 5px;"><p>x</p></section>',
            content_samples=["x"],
            format_desc="[border=2pxsolidred;padding=5px]",
        )],
    )
    html_path = tmp_path / "t.html"
    html_path.write_text(
        '<html><body><article><section><section style="border:1px"><p>占位</p></section></section></article></body></html>',
        encoding="utf-8",
    )
    draft = [{"level": 1, "text": "摘要内容"}, {"level": 1, "text": "关键字内容"}]
    result = replace_template(html_path, tpl, draft)
    soup = BeautifulSoup(result, "lxml")
    blocks = [c for c in soup.find("article").find("section").children
              if hasattr(c, "name") and c.name == "section"]
    assert len(blocks) == 2  # 特殊层级不合并
    assert "摘要内容" in result and "关键字内容" in result


def test_is_plain_body_classification():
    """_is_plain_body：标题/带边框/带背景的都 False，纯正文 True。"""
    heading = LevelInfo(level_id=1, sig_hash="a", font_size=24, color="x",
                       is_heading=True, block_count=1, html_sample="", content_samples=[])
    bordered = LevelInfo(level_id=2, sig_hash="b", font_size=14, color="x",
                         is_heading=False, block_count=1, html_sample="", content_samples=[],
                         format_desc="[border=2pxsolidred]")
    bg = LevelInfo(level_id=3, sig_hash="c", font_size=14, color="x",
                  is_heading=False, block_count=1, html_sample="", content_samples=[],
                  format_desc="[background-color=rgb(255,255,255)]")
    plain = LevelInfo(level_id=4, sig_hash="d", font_size=14, color="x",
                     is_heading=False, block_count=1, html_sample="", content_samples=[],
                     format_desc="[margin=10px]")
    assert not _is_plain_body(heading)
    assert not _is_plain_body(bordered)
    assert not _is_plain_body(bg)
    assert _is_plain_body(plain)


def test_replace_template_fixes_page_title(tmp_path):
    """模板 <title> 和 <h1> 文字换成新稿大标题（遗留问题）。"""
    tpl = _fake_template()
    html_path = tmp_path / "t.html"
    html_path.write_text(
        '<html><head><title>旧模板标题</title></head>'
        '<body><main><h1>旧H1标题</h1></main>'
        '<article><section><section style="font-size:24px"><p>占位</p></section></section></article>'
        '</body></html>',
        encoding="utf-8",
    )
    draft = [{"level": 1, "text": "新稿大标题"}]
    result = replace_template(html_path, tpl, draft)
    soup = BeautifulSoup(result, "lxml")
    assert soup.find("title").string == "新稿大标题"
    assert soup.body.find("h1").string == "新稿大标题"
    assert "旧模板标题" not in result
    assert "旧H1标题" not in result
