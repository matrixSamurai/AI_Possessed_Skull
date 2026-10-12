"""Read-only ElevenLabs agent configuration check; never prints keys or prompts."""

from malachi.config import Settings


def agent_summary(agent):
    config = getattr(agent, "conversation_config", None)
    conversation = getattr(config, "conversation", None)
    files = getattr(conversation, "file_input", None)
    prompt = getattr(getattr(config, "agent", None), "prompt", None)
    text = getattr(prompt, "prompt", "") or ""
    enabled = getattr(files, "enabled", None)
    platform = getattr(agent, "platform_settings", None)
    overrides = getattr(platform, "overrides", None)
    override_config = getattr(overrides, "conversation_config_override", None)
    agent_override = getattr(override_config, "agent", None)
    return {
        "file_input": "enabled"
        if enabled is True
        else "disabled"
        if enabled is False
        else "not declared",
        "llm": getattr(prompt, "llm", None) or "not declared",
        "legacy_visual_variable": "{{visual_context}}" in text,
        "first_message_empty": getattr(getattr(config, "agent", None), "first_message", None) == "",
        "first_message_override_allowed": getattr(agent_override, "first_message", None) is True,
    }


def check_agent(settings, transport_factory=None):
    from elevenlabs.client import ElevenLabs
    import httpx

    key = settings.elevenlabs_api_key.get_secret_value()
    if not key or not settings.elevenlabs_agent_id:
        raise ValueError("Missing local ElevenLabs credentials")
    factory = transport_factory or httpx.Client
    with factory(timeout=10) as transport:
        client = ElevenLabs(
            api_key=key, base_url="https://api.elevenlabs.io", httpx_client=transport
        )
        agent = client.conversational_ai.agents.get(
            agent_id=settings.elevenlabs_agent_id,
            request_options={"max_retries": 0, "timeout_in_seconds": 10},
        )
    return agent_summary(agent)


def main():
    settings = Settings()
    print("Local image uploads:", "enabled" if settings.vision_context_enabled else "disabled")
    print("Conversation backend:", settings.conversation_backend)
    if not settings.vision_context_enabled:
        print("Set VISION_CONTEXT_ENABLED=true in .env and restart the app.")
    try:
        summary = check_agent(settings)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        print(
            "Agent config check failed:", type(exc).__name__, f"(HTTP {status})" if status else ""
        )
        print(
            "Check local credentials and permission to read this agent. No conversation was started."
        )
        return 1
    print("Agent file input:", summary["file_input"])
    print("Agent LLM:", summary["llm"])
    print("Agent first message empty:", summary["first_message_empty"])
    print("First-message override allowed:", summary["first_message_override_allowed"])
    print("Prompt uses legacy visual_context variable:", summary["legacy_visual_variable"])
    print(
        "This checks configuration only; it does not prove image delivery or model interpretation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
