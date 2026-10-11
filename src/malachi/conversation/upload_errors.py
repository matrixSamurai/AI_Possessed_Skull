"""Bounded, redacted upload rejection hints; never dump an API response."""

import json
import re


def upload_error_hint(error, settings):
    body = getattr(error, "body", None)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (ValueError, TypeError):
            return ""  # Do not display raw HTML, response dumps or arbitrary strings.
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        message = detail.get("message", detail.get("msg", ""))
    elif isinstance(detail, str):
        message = detail
    else:
        return ""  # Validation lists can include original file bytes; omit them.
    if not isinstance(message, str):
        return ""
    for secret in [settings.elevenlabs_api_key.get_secret_value(), settings.elevenlabs_agent_id]:
        if secret:
            message = message.replace(secret, "[redacted]")
    message = re.sub(r"(?:https?|wss?)://\S+", "[url redacted]", message)
    message = re.sub(r"(?i)bearer\s+\S+|\bsk_[A-Za-z0-9_-]+", "[key redacted]", message)
    message = re.sub(r"[A-Za-z0-9+/=_-]{40,}", "[data redacted]", message)
    message = " ".join(message.split())
    return message[:240]
