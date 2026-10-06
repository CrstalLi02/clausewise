"""Tests for auth tokens and identity boundaries."""
from __future__ import annotations

import time

from app.auth import AuthService
from app.config import Settings
from app.storage.store import MemoryStore


def test_token_contains_expiry_and_verifies():
    settings = Settings(storage_mode="memory", auth_secret="test-secret", auth_token_ttl_hours=1)
    auth = AuthService(MemoryStore(), settings)
    token = auth.issue_token("student")
    assert token.startswith("v1.")
    assert auth.verify_token(token) == "student"
    assert auth.verify_token(token + "tampered") is None


def test_expired_token_is_rejected(monkeypatch):
    settings = Settings(storage_mode="memory", auth_secret="test-secret", auth_token_ttl_hours=1)
    auth = AuthService(MemoryStore(), settings)
    monkeypatch.setattr(time, "time", lambda: 1000)
    token = auth.issue_token("student")
    monkeypatch.setattr(time, "time", lambda: 5000)
    assert auth.verify_token(token) is None
