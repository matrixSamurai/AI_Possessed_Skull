from types import SimpleNamespace
from malachi.conversation.upload_errors import upload_error_hint


def test_useful_upload_reason_with_secret_redaction(settings):
    settings.elevenlabs_api_key = "test-key-never-display"
    settings.elevenlabs_agent_id = "agent-private"
    error = SimpleNamespace(
        body={
            "detail": {
                "message": "File input requires a text-only conversation. test-key-never-display agent-private "
                "https://example.invalid/token?key=other Bearer abcdef sk_othersecret"
            }
        }
    )
    hint = upload_error_hint(error, settings)
    assert "text-only conversation" in hint
    for value in [
        "test-key-never-display",
        "agent-private",
        "example.invalid",
        "abcdef",
        "sk_othersecret",
    ]:
        assert value not in hint


def test_never_dumps_file_data_or_html(settings):
    for body in ["<html>private response</html>", {"detail": [{"input": "private-file-bytes"}]}]:
        assert upload_error_hint(SimpleNamespace(body=body), settings) == ""
    hint = upload_error_hint(
        SimpleNamespace(body={"detail": "Invalid image " + "A" * 1000}), settings
    )
    assert "[data redacted]" in hint and len(hint) <= 240


def test_json_string_response_is_parsed_without_dump(settings):
    error = SimpleNamespace(
        body='{"detail":{"message":"Model does not support images"},"private":"hidden"}'
    )
    assert upload_error_hint(error, settings) == "Model does not support images"
    assert upload_error_hint(RuntimeError("private exception"), settings) == ""


def test_connection_diagnostics_show_code_without_signed_url(settings):
    from types import SimpleNamespace
    from malachi.conversation.upload_errors import connection_error_hint

    class Closed(Exception):
        rcvd = SimpleNamespace(code=1011, reason="secret wss://private.invalid/signed")

    hint = connection_error_hint(Closed("secret URL"), settings)
    assert hint == "Closed: WebSocket close 1011"
    assert "secret" not in hint


def test_service_error_message_is_redacted(settings):
    from malachi.conversation.elevenlabs_client import ElevenLabsServiceError
    from malachi.conversation.upload_errors import connection_error_hint

    settings.elevenlabs_api_key = "test-secret"
    error = ElevenLabsServiceError(
        {"type": "error", "error_event": {"message": "File limit reached test-secret"}}
    )
    hint = connection_error_hint(error, settings)
    assert "File limit reached" in hint and "test-secret" not in hint


def test_policy_close_classifies_override_without_exposing_reason(settings):
    from malachi.conversation.upload_errors import connection_error_hint

    class Closed(Exception):
        rcvd = SimpleNamespace(
            code=1008, reason="first_message override not allowed secret wss://private.invalid"
        )

    hint = connection_error_hint(Closed(), settings)
    assert "first-message policy rejected" in hint
    assert "secret" not in hint and "private.invalid" not in hint
