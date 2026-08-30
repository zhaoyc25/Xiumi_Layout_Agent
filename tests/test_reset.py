import pytest

from xiumi_layout_agent.chat.tools import Session, build_default_registry


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    from xiumi_layout_agent.chat import config as cfg
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / ".gitkeep").touch()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(cfg, "_REPO_ROOT", tmp_path)
    return tmp_path


def test_reset_all_not_in_default_names():
    reg = build_default_registry(Session())
    assert "reset_all" in reg.names()


def test_reset_all_clears_projects_and_inbox(workspace):
    (workspace / "workspace" / "20260831_demo").mkdir()
    (workspace / "workspace" / "20260831_demo" / "input").mkdir()
    (workspace / "workspace" / "20260831_demo" / "input" / "a.txt").write_text("x")
    (workspace / "inbox" / "图1.png").write_bytes(b"\x89PNG")

    s = Session()
    s.data["task_id"] = "20260831_demo"
    reg = build_default_registry(s)
    out = reg.get("reset_all").run({})

    assert "已清空" in out
    assert list((workspace / "workspace").iterdir()) == [(workspace / "workspace" / ".gitkeep")]
    assert list((workspace / "inbox").iterdir()) == []
    assert s.data == {}


def test_reset_all_on_empty(workspace):
    reg = build_default_registry(Session())
    out = reg.get("reset_all").run({})
    assert "本来就是空的" in out


def test_reset_all_keeps_gitkeep(workspace):
    (workspace / "inbox" / "x.txt").write_text("x")
    reg = build_default_registry(Session())
    reg.get("reset_all").run({})
    assert (workspace / "workspace" / ".gitkeep").exists()
