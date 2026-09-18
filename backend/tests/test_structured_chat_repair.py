"""claude/client.py structured_chat — TESTING_FINDINGS2.md, 2026-09-18: a
tool call missing a required field (e.g. planning's target_keywords) used to
only be caught at the job level, where worker/retry.py re-runs the *exact
same* prompt after a 2/4-minute backoff with no feedback about what was
missing — slow, and no more likely to succeed the second time. structured_chat
now repairs in-conversation: it tells the model what it omitted and asks it
to resubmit, before the job-level retry is ever needed."""

from types import SimpleNamespace

import claude.client as client


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, name, input_, id_):
        self.name = name
        self.input = input_
        self.id = id_


def _response(input_, *, name="build_plan", id_="tool_1"):
    return SimpleNamespace(
        content=[_FakeToolUseBlock(name, input_, id_)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def test_repairs_a_response_missing_a_required_field(fake_db, monkeypatch):
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response({"outline": {"sections": []}})  # target_keywords omitted
        return _response({"outline": {"sections": []}, "target_keywords": ["kw"]})

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))
    monkeypatch.setattr(client, "_client", lambda: fake_client)

    result = client.structured_chat(
        model="claude-x",
        system="sys",
        user_message="do the thing",
        output_schema={"type": "object", "required": ["outline", "target_keywords"]},
        tool_name="build_plan",
    )

    assert result == {"outline": {"sections": []}, "target_keywords": ["kw"]}
    assert len(calls) == 2
    # the repair turn told the model exactly what it omitted
    repair_message = calls[1]["messages"][-1]
    assert repair_message["role"] == "user"
    assert "target_keywords" in repair_message["content"][0]["content"]


def test_gives_up_after_max_repairs_and_returns_last_result(fake_db, monkeypatch):
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return _response({"outline": {"sections": []}})  # always missing target_keywords

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))
    monkeypatch.setattr(client, "_client", lambda: fake_client)

    result = client.structured_chat(
        model="claude-x",
        system="sys",
        user_message="do the thing",
        output_schema={"type": "object", "required": ["outline", "target_keywords"]},
        tool_name="build_plan",
    )

    assert result == {"outline": {"sections": []}}
    assert len(calls) == client.MAX_STRUCTURED_REPAIRS + 1
