from types import SimpleNamespace
import pytest
from malachi.diagnostics import agent_summary, check_agent


def test_actual_sdk_read_only_agent_config(settings):
    import httpx

    settings.elevenlabs_agent_id = "agent_test"
    settings.elevenlabs_api_key = "test-secret-not-real"
    calls = []

    def handle(request):
        calls.append(request)
        assert request.method == "GET" and request.url.path == "/v1/convai/agents/agent_test"
        return httpx.Response(
            200,
            json={
                "agent_id": "agent_test",
                "name": "test",
                "conversation_config": {
                    "conversation": {"file_input": {"enabled": True}},
                    "agent": {
                        "prompt": {
                            "llm": "gpt-4o",
                            "prompt": "private prompt {{visual_context}} test-secret",
                        }
                    },
                },
                "metadata": {},
            },
        )

    result = check_agent(
        settings, lambda **kw: httpx.Client(transport=httpx.MockTransport(handle), **kw)
    )
    assert result == {
        "file_input": "enabled",
        "llm": "gpt-4o",
        "legacy_visual_variable": True,
        "first_message_empty": False,
        "first_message_override_allowed": False,
    }
    assert (
        len(calls) == 1 and "test-secret" not in str(result) and "private prompt" not in str(result)
    )


def test_unavailable_config_is_not_reported_as_enabled():
    assert agent_summary(SimpleNamespace()) == {
        "file_input": "not declared",
        "llm": "not declared",
        "legacy_visual_variable": False,
        "first_message_empty": False,
        "first_message_override_allowed": False,
    }


def test_missing_key_does_not_make_network_request(settings):
    with pytest.raises(ValueError):
        check_agent(settings, lambda **kw: pytest.fail("No request without credentials"))


def test_greeting_permissions_follow_actual_nested_agent_config():
    agent = SimpleNamespace(
        conversation_config=SimpleNamespace(agent=SimpleNamespace(first_message="")),
        platform_settings=SimpleNamespace(
            overrides=SimpleNamespace(
                conversation_config_override=SimpleNamespace(
                    agent=SimpleNamespace(first_message=True)
                )
            )
        ),
    )
    summary = agent_summary(agent)
    assert summary["first_message_empty"] and summary["first_message_override_allowed"]
