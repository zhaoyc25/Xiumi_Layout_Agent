from xiumi_layout_agent.chat.config import LLMConfig, load_llm_config
from xiumi_layout_agent.chat.llm import MockLLM


def test_load_config_missing(monkeypatch, tmp_path):
    for k in ("XIUMI_LLM_API_KEY", "XIUMI_LLM_BASE_URL", "XIUMI_LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("xiumi_layout_agent.chat.config._CONFIG_ENV", tmp_path / "no.env")
    assert load_llm_config() is None


def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("XIUMI_LLM_API_KEY", "k")
    monkeypatch.setenv("XIUMI_LLM_BASE_URL", "https://x")
    monkeypatch.setenv("XIUMI_LLM_MODEL", "m")
    cfg = load_llm_config()
    assert cfg == LLMConfig(api_key="k", base_url="https://x", model="m")


def test_mock_llm_script_and_calls():
    m = MockLLM(replies=["一", "二"])
    assert m.chat([{"role": "user", "content": "q"}]) == "一"
    assert m.chat([]) == "二"
    assert len(m.calls) == 2


def test_mock_llm_dynamic():
    m = MockLLM()
    m.on_message(lambda msgs: "动态")
    assert m.chat([]) == "动态"
