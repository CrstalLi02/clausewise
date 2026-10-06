"""Test fixtures."""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.deps import build_container
from app.llm.embeddings import EmbeddingClient
from app.pipeline.parser import DocumentParser


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def container(settings):
    """Offline container (memory storage + hash vectors + no real LLM)."""
    return build_container(settings)


@pytest.fixture
def fresh_container(settings):
    """An independent offline container for each test."""
    return build_container(settings)


@pytest.fixture
def parser():
    return DocumentParser()


@pytest.fixture
def embeddings(settings):
    return EmbeddingClient(settings, relay=None)
