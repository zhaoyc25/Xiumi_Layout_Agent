from xiumi_layout_agent.chat.tools import Session, Tool, ToolRegistry, build_default_registry


def test_registry_register_and_get():
    reg = ToolRegistry()
    reg.register(Tool("t1", "测试工具", {"type": "object", "properties": {}}, lambda a: "ok"))
    assert reg.get("t1") is not None
    assert reg.get("nope") is None
    assert reg.names() == ["t1"]


def test_duplicate_name_rejected():
    reg = ToolRegistry()
    reg.register(Tool("t1", "d", {}, lambda a: "ok"))
    try:
        reg.register(Tool("t1", "d2", {}, lambda a: "ok"))
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate should fail")


def test_tool_internal_error_captured():
    def boom(_):
        raise RuntimeError("炸了")
    reg = ToolRegistry()
    reg.register(Tool("bad", "d", {}, boom))
    out = reg.get("bad").run({})
    assert "出错了" in out and "炸了" in out


def test_default_registry_stubs():
    reg = build_default_registry(Session())
    assert set(reg.names()) == {
        "new_project", "reset_all", "scan_inbox", "normalize_draft", "review_levels",
        "build_template_map", "replace_template", "upload_images", "deliver_result",
    }
    # scan_inbox / build_template_map / normalize_draft 已落地，不再是桩
    assert "任务号" in reg.get("scan_inbox").run({})
    assert "任务号" in reg.get("build_template_map").run({})
    # normalize_draft 无 task_id 时报错（不是"功能未实现"桩）
    assert "功能未实现" not in reg.get("normalize_draft").run({})
    # 其余仍是桩
    assert "功能未实现" in reg.get("review_levels").run({})
    assert "功能未实现" in reg.get("replace_template").run({})


def test_new_project_records_task_id():
    s = Session()
    reg = build_default_registry(s)
    reg.get("new_project").run({"task_id": "20260830_test"})
    assert s.data["task_id"] == "20260830_test"
