"""Tests for duplicate files and version chains."""
from __future__ import annotations

import pytest

from app.pipeline.indexer import DuplicateDocumentError


@pytest.mark.asyncio
async def test_duplicate_and_version_chain(fresh_container, tmp_path):
    c = fresh_container
    first = tmp_path / "policy.txt"
    first.write_text("Chapter 1 General Provisions\nArticle 1 Original version of the rule.", encoding="utf-8")
    d1 = await c.indexer.ingest(first, "dept_test")
    assert d1["version"] == "1.0"
    with pytest.raises(DuplicateDocumentError):
        await c.indexer.ingest(first, "dept_test")

    first.write_text("Chapter 1 General Provisions\nArticle 1 The new version of the rule has been updated.", encoding="utf-8")
    d2 = await c.indexer.ingest(first, "dept_test")
    assert d2["version"] == "1.1"
    assert d2["supersedes"] == d1["_id"]
    assert (await c.store.get_document(d1["_id"]))["status"] == "archived"
    assert (await c.store.get_document(d2["_id"]))["status"] == "active"
