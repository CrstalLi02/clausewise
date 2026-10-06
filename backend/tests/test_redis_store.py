from app.storage.redis_store import _redact_redis_addr


def test_redact_redis_addr_hides_password() -> None:
    redacted = _redact_redis_addr("redis://user:secret@redis:6379/0")

    assert redacted == "redis://user:***@redis:6379/0"
    assert "secret" not in redacted


def test_redact_redis_addr_supports_password_only_and_plain_urls() -> None:
    assert _redact_redis_addr("redis://:secret@redis:6379") == "redis://***@redis:6379"
    assert _redact_redis_addr("redis://redis:6379") == "redis://redis:6379"
