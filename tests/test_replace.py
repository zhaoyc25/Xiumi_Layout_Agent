"""replace/core.py 测试：克隆模板节点+替换文字+清理图片+拼装。"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from xiumi_layout_agent.replace.core import _clean_images, _replace_text, replace_template
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
