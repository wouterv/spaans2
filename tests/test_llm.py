from types import SimpleNamespace

import pytest

from app import llm


def _fake_client(monkeypatch, *, text='{"ok": true}', stop_reason="end_turn"):
    """Vervang de echte Anthropic-client door een nep-client."""
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
    )
    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return response

    monkeypatch.setattr(
        llm, "_client", lambda: SimpleNamespace(messages=FakeMessages())
    )
    return calls


SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}


def test_complete_json_parst_de_json(monkeypatch):
    _fake_client(monkeypatch, text='{"correct": true, "feedback": ""}')
    result = llm.complete_json("systeem", [{"role": "user", "content": "hoi"}], SCHEMA)
    assert result == {"correct": True, "feedback": ""}


def test_complete_json_stuurt_schema_en_model_mee(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")
    llm.complete_json("systeem", [{"role": "user", "content": "hoi"}], SCHEMA)
    assert calls[0]["model"] == "claude-haiku-4-5"
    assert calls[0]["output_config"] == {
        "format": {"type": "json_schema", "schema": SCHEMA}
    }
    assert calls[0]["system"] == "systeem"
    assert calls[0]["thinking"] == {"type": "adaptive"}


def test_default_model(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)
    assert calls[0]["model"] == llm.DEFAULT_MODEL


def test_ontbrekende_api_key_geeft_llmerror(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)


def test_onbruikbare_json_geeft_llmerror(monkeypatch):
    _fake_client(monkeypatch, text="dit is geen json")
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)


def test_weigering_geeft_llmerror(monkeypatch):
    _fake_client(monkeypatch, stop_reason="refusal")
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)


def test_api_fout_geeft_nederlandse_llmerror(monkeypatch):
    import anthropic

    class FakeMessages:
        def create(self, **kwargs):
            raise anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(
        llm, "_client", lambda: SimpleNamespace(messages=FakeMessages())
    )
    with pytest.raises(llm.LLMError) as excinfo:
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)
    assert "verbinding" in str(excinfo.value).lower()


def test_cache_system_stuurt_cache_control_mee(monkeypatch):
    calls = _fake_client(monkeypatch)
    llm.complete_json(
        "systeem", [{"role": "user", "content": "hoi"}], SCHEMA, cache_system=True
    )
    assert calls[0]["system"] == [{
        "type": "text",
        "text": "systeem",
        "cache_control": {"type": "ephemeral"},
    }]


def test_zonder_cache_system_blijft_system_een_string(monkeypatch):
    calls = _fake_client(monkeypatch)
    llm.complete_json("systeem", [{"role": "user", "content": "hoi"}], SCHEMA)
    assert calls[0]["system"] == "systeem"
