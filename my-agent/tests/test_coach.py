from coach import COACH_INSTRUCTIONS, DEFAULT_AGENT_NAME, agent_name


def test_agent_name_defaults_to_production_dispatch(monkeypatch):
    monkeypatch.delenv("AGENT_NAME", raising=False)
    assert agent_name() == DEFAULT_AGENT_NAME


def test_agent_name_override_for_dev_workers(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "  coach-diego ")
    assert agent_name() == "coach-diego"


def test_blank_agent_name_falls_back(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "   ")
    assert agent_name() == DEFAULT_AGENT_NAME


def test_instructions_cover_every_session_phase():
    for phase in ("Setup.", "Research.", "Listen.", "Feedback.", "Next round."):
        assert phase in COACH_INSTRUCTIONS
    assert "I'm done" in COACH_INSTRUCTIONS
