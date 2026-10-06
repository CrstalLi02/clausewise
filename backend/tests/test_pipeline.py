"""Tests for parsing/cleaning/ingestion (offline)."""
from __future__ import annotations

import pytest

from app.pipeline.cleaner import TextCleaner
from app.pipeline.chunker import Chunker
from app.pipeline.parser import Block, DocumentParser, ParsedDocument


def test_parse_text(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("Chapter 1 General Provisions\nArticle 1 This is the policy content.\nArticle 2 This is another article.", encoding="utf-8")
    doc = DocumentParser().parse(p)
    assert doc.blocks
    assert any(b.type == "heading" for b in doc.blocks)


def test_parse_markdown(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# Course Registration Rules\n\n- Item one\n- Item two\n", encoding="utf-8")
    doc = DocumentParser().parse(p)
    assert doc.blocks[0].type == "heading"
    assert doc.blocks[0].text == "Course Registration Rules"


def test_cleaner_fullwidth():
    cleaner = TextCleaner()
    assert cleaner.clean_text("Full-width：１２３") == "Full-width:123"


def test_cleaner_removes_noise():
    cleaner = TextCleaner()
    doc = ParsedDocument(title="t", blocks=[Block(type="paragraph", level=0, text="Page 1 of 3")])
    out = cleaner.clean(doc)
    assert out.blocks == []
