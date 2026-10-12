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


def connection_error_hint(error, settings):
    """Report structured service hints and socket codes, never raw exception strings."""
    parts = [type(error).__name__]
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        parts.append(f"HTTP {status}")
    received = getattr(error, "rcvd", None)
    code = getattr(received, "code", None)
    if isinstance(code, int):
        parts.append(f"WebSocket close {code}")
        reason = getattr(received, "reason", "")
        if code == 1008 and isinstance(reason, str):
            # Only named categories are exposed, never arbitrary close-reason text.
            reason = reason.lower()
            if "override" in reason or "first_message" in reason or "first message" in reason:
                parts.append("agent client override/first-message policy rejected")
            elif "quota" in reason or "limit" in reason:
                parts.append("service quota/limit policy rejected")
            elif "file" in reason or "image" in reason:
                parts.append("service image/file policy rejected")
            else:
                parts.append("service policy rejected; inspect ElevenLabs conversation diagnostics")
    hint = upload_error_hint(error, settings)
    if hint:
        parts.append(hint)
    return ": ".join(parts)
