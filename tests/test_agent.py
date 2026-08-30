from xiumi_layout_agent.chat.agent import Agent
from xiumi_layout_agent.chat.llm import MockLLM
from xiumi_layout_agent.chat.tools import Session, build_default_registry
from xiumi_layout_agent.chat.workflow import Stage, WorkflowState


def _agent(replies=None):
    llm = MockLLM(replies=replies)
    session = Session()
    agent = Agent(llm, build_default_registry(session), session, WorkflowState())
    return agent, llm


def test_speak_direct():
    agent, llm = _agent()
    llm.on_message(lambda msgs: "SPEAK 您好呀")
    assert agent.handle("你好") == "您好呀"


def test_plain_reply_treated_as_speak():
    agent, llm = _agent()
    llm.on_message(lambda msgs: "老师您好，请把文件放进文件夹")
    assert "文件" in agent.handle("在吗")


def test_tool_call_then_speak():
    agent, llm = _agent()
    seq = [
        'CALL new_project {"task_id": "20260831_demo"}',
        "SPEAK 好嘞，新项目记上了，请把模板文件放进文件夹",
    ]
    llm.on_message(lambda msgs: seq.pop(0) if seq else "SPEAK 完毕")
    out = agent.handle("开个新项目，就用 demo 这个名字")
    assert "新项目" in out
    assert agent.session.data["task_id"] == "20260831_demo"
    # 第二轮 LLM 收到了工具结果
    tool_msg = [m for m in llm.calls[1] if "工具 new_project 结果" in m["content"]]
    assert tool_msg, "tool result should be fed back"


def test_unknown_tool_retry():
    agent, llm = _agent()
    seq = ["CALL no_such_tool {}", "SPEAK 抱歉刚才记错了，已为您登记"]
    llm.on_message(lambda msgs: seq.pop(0) if seq else "SPEAK 完毕")
    out = agent.handle("开始")
    assert "登记" in out


def test_infinite_loop_guard():
    agent, _ = _agent()
    agent.llm = MockLLM()  # 无脚本 -> 固定回复含 CALL
    agent.llm.on_message(lambda msgs: 'CALL new_project {"task_id": "x"}')
    out = agent.handle("开始")
    assert "再说一遍" in out


def test_system_prompt_contains_stage_and_persona():
    agent, llm = _agent()
    llm.on_message(lambda msgs: "SPEAK ok")
    agent.handle("hi")
    sys_msg = llm.calls[0][0]["content"]
    assert sys_msg.startswith("你是秀米排版小助手")
    assert "idle" in sys_msg
    assert agent.workflow.stage is Stage.IDLE
