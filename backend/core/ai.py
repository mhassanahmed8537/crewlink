import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

PUSH_PREVIEW_MAX_CHARS = 120

SYSTEM_PROMPT = (
    "You turn a busy union leader's rough, shorthand note into a clear announcement. "
    "Reply with strict JSON only, no prose outside the JSON, matching this shape: "
    '{"title": "...", "body": "...", "push_preview": "..."}. '
    "title is a short, plain heading. body is one to three clear sentences, "
    "no shorthand, no ALL CAPS shouting, keep every concrete fact from the input: "
    "who, what, where, when. push_preview is 120 characters or fewer, plain text, "
    "safe to truncate at 120 characters if you go over."
)


class AIProviderUnavailable(Exception):
    """Raised whenever a draft could not be generated, for any reason."""


def _client():
    if not settings.ANTHROPIC_API_KEY:
        raise AIProviderUnavailable("No AI provider is configured.")
    import anthropic

    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS,
        max_retries=0,
    )


def generate_draft(raw_text: str) -> dict:
    """
    Turn a messy note into a title, body, and push preview.

    Raises AIProviderUnavailable if the provider is not configured, too
    slow, or errors out. The caller is expected to fall back to a blank,
    manually written draft when that happens, never to send anything the
    provider produced without a human seeing it first.
    """
    client = _client()

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": raw_text}],
        )
    except Exception as exc:
        logger.warning("AI draft generation failed: %s", exc)
        raise AIProviderUnavailable(str(exc)) from exc

    raw = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

    try:
        parsed = json.loads(raw)
        title = str(parsed["title"]).strip()
        body = str(parsed["body"]).strip()
        push_preview = str(parsed["push_preview"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("AI draft response was not the expected JSON shape: %s", raw[:200])
        raise AIProviderUnavailable("The provider returned an unexpected response shape.") from exc

    if len(push_preview) > PUSH_PREVIEW_MAX_CHARS:
        push_preview = push_preview[: PUSH_PREVIEW_MAX_CHARS - 1].rstrip() + "…"

    return {"title": title, "body": body, "push_preview": push_preview}
