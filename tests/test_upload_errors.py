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
