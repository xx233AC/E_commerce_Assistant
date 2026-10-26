"""Per-call audit collection. Contains no credentials and is never a public API DTO."""
from contextlib import contextmanager
from contextvars import ContextVar

_collector = ContextVar("llm_call_audit", default=None)


@contextmanager
def capture_call():
    metadata = {}
    token = _collector.set(metadata)
    try:
        yield metadata
    finally:
        _collector.reset(token)


def record_response(provider_id, usage, raw_output):
    metadata = _collector.get()
    if metadata is None:
        return
    allowed = {"prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"}
    metadata["usage"] = {key: value for key, value in (usage or {}).items()
                         if key in allowed and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
    metadata["provider_request_id"] = str(provider_id)[:200] if provider_id else None
    # This is the model's JSON text, not an HTTP response or request containing Authorization.
    metadata["raw_output"] = raw_output

