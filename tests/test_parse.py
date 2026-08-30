import json

from xiumi_layout_agent.chat.agent import Agent


def test_parse_call():
    name, args, speak = Agent._parse('CALL new_project {"task_id": "t1"}')
    assert name == "new_project"
    assert args == {"task_id": "t1"}
    assert speak is None


def test_parse_call_no_args():
    name, args, _ = Agent._parse("CALL scan_inbox")
    assert name == "scan_inbox"
    assert args == {}


def test_parse_call_bad_json():
    name, args, _ = Agent._parse("CALL scan_inbox {bad json}")
    assert name == "scan_inbox"
    assert args == {}


def test_parse_speak():
    _, _, speak = Agent._parse("SPEAK 老师您好")
    assert speak == "老师您好"


def test_parse_plain():
    name, _, speak = Agent._parse("随便一句话")
    assert name is None
    assert speak == "随便一句话"


def test_parse_json_roundtrip():
    args = {"task_id": "20260831_会", "中文": "值"}
    _, parsed, _ = Agent._parse(f"CALL new_project {json.dumps(args, ensure_ascii=False)}")
    assert parsed == args
