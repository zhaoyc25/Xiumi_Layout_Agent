"""本地文章导入微信扩展的静态契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "wechat_import_extension"


def test_manifest_has_minimal_wechat_permissions():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["permissions"] == ["tabs", "scripting"]
    assert manifest["host_permissions"] == ["https://mp.weixin.qq.com/*"]
    assert manifest["action"]["default_popup"] == "popup.html"


def test_popup_loads_external_script_and_article_fields():
    html = (ROOT / "popup.html").read_text(encoding="utf-8")
    assert '<script src="popup.js"></script>' in html
    for field_id in ("file", "target", "title", "desc", "author", "link", "import"):
        assert f'id="{field_id}"' in html


def test_script_guards_images_and_never_saves_or_publishes():
    script = (ROOT / "popup.js").read_text(encoding="utf-8")
    assert "localImageSources" in script
    assert "https?:|data:" in script
    assert "mp_editor_set_content" in script
    assert "chrome.scripting.executeScript" in script
    assert "publish" not in script.lower()
    assert "save" not in script.lower()
