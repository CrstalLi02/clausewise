"""Tests for semantic chunking."""
from __future__ import annotations

from app.pipeline.chunker import Chunker
from app.pipeline.parser import Block, ParsedDocument


def _doc(blocks):
    return ParsedDocument(title="Test Regulation", blocks=blocks)


def test_basic_chunking():
    blocks = [
        Block(type="heading", level=1, text="Chapter 1 General Provisions"),
        Block(type="paragraph", level=0, text="Article 1 " + "policy content " * 30),
        Block(type="paragraph", level=0, text="Article 2 " + "clause content " * 30),
    ]
    chunks = Chunker(min_chars=100, max_chars=400).chunk(_doc(blocks))
    assert chunks, "Should produce at least one chunk"
    for c in chunks:
        assert c["content"]
        assert c["content_hash"]
        assert c["char_count"] == len(c["content"])
        assert c["section_path"][0] == "Chapter 1 General Provisions"


def test_chunk_respects_size_bounds():
    blocks = [Block(type="paragraph", level=0, text="Article X " + "very long clause content " * 84)]
    chunks = Chunker(min_chars=200, max_chars=600).chunk(_doc(blocks))
    assert len(chunks) >= 2
    assert all(c["char_count"] <= 650 for c in chunks)


def test_empty_document():
    chunks = Chunker().chunk(_doc([]))
    assert chunks == []
