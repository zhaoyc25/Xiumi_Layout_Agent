"""template/extract.py 测试：模板 HTML 结构提取。"""

from __future__ import annotations

from pathlib import Path

from xiumi_layout_agent.template.extract import extract_template

# 一个迷你 xiumi 风格 HTML：4 个不同嵌入格式的层级
_SAMPLE_HTML = """<!DOCTYPE html>
<html><body>
<article>
<section>
  <section style="display: flex; text-align: center; justify-content: center; box-sizing: border-box;">
    <section style="display: inline-block; background-color: rgb(145,184,186); border-radius: 0px 26px; padding: 5px 15px; box-sizing: border-box;">
      <section style="font-size: 24px; color: rgb(255,255,255); box-sizing: border-box;">
        <p><b>一、大标题</b></p>
      </section>
    </section>
  </section>
  <p></p>
  <section style="text-align: left; transform: translate3d(15px,0,0); box-sizing: border-box;">
    <section style="font-size: 20px; color: rgb(255,255,255); letter-spacing: 5px; box-sizing: border-box;">
      <p>1.二级标题</p>
    </section>
  </section>
  <p></p>
  <section style="display: flex; text-align: center; justify-content: center; box-sizing: border-box;">
    <section style="display: inline-block; width: 87%; background-color: rgb(255,255,255); padding: 15px 26px; box-sizing: border-box;">
      <section style="text-align: justify; box-sizing: border-box;">
        <p>        这是正文段落，用于测试正文层级的提取是否正确。我们正在验证BeautifulSoup能否正确识别不同嵌入格式的层级结构。</p>
      </section>
    </section>
  </section>
  <p></p>
  <section style="text-align: left; box-sizing: border-box;">
    <section style="text-align: center; font-size: 12px; color: rgb(163,163,163); letter-spacing: 1px; box-sizing: border-box;">
      <p>文案 | 测试编辑部</p>
    </section>
  </section>
</section>
</article>
</body></html>"""


def _write_sample(tmp_path: Path) -> Path:
    p = tmp_path / "sample.html"
    p.write_text(_SAMPLE_HTML, encoding="utf-8")
    return p


def test_extract_finds_levels(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    assert len(ts.levels) == 4


def test_extract_font_sizes(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    fss = [lv.font_size for lv in ts.levels]
    assert fss == sorted(fss, reverse=True)  # 从大到小排
    assert 24 in fss
    assert 20 in fss
    assert 14 in fss or 12 in fss


def test_extract_html_sample(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    for lv in ts.levels:
        assert "<section" in lv.html_sample
        assert lv.html_sample.strip().startswith("<section")


def test_extract_content_samples(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    all_text = []
    for lv in ts.levels:
        all_text.extend(lv.content_samples)
    assert any("大标题" in t for t in all_text)
    assert any("二级标题" in t for t in all_text)
    assert any("正文段落" in t for t in all_text)
    assert any("文案" in t for t in all_text)


def test_extract_is_heading(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    heading_levels = [lv for lv in ts.levels if lv.is_heading]
    body_levels = [lv for lv in ts.levels if not lv.is_heading]
    assert len(heading_levels) >= 3   # 大标题、二级标题、落款
    assert len(body_levels) >= 1      # 正文


def test_extract_render_summary(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    summary = ts.render_summary()
    assert "模板结构" in summary
    assert "层级" in summary
    assert "px" in summary


def test_extract_to_dict(tmp_path):
    p = _write_sample(tmp_path)
    ts = extract_template(p)
    d = ts.to_dict()
    assert "source_file" in d
    assert "levels" in d
    assert len(d["levels"]) == 4
