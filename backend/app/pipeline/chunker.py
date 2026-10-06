"""Semantic chunking: splits along clause-level semantic boundaries (chapter/section/article/clause), targeting 300-600 characters.

Instead of hard-splitting by a fixed token count, this keeps every answer traceable to a specific clause.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

from app.pipeline.parser import Block, ParsedDocument

# Target chunk size (characters)
MIN_CHARS = 300
MAX_CHARS = 600

# Clause boundaries: Article X / Chapter X / numbering / I. II. ...
CLAUSE_RE = re.compile(
    r"^((?:Chapter|Section|Article|Clause|Part)\s+(?:\d+|[IVXLC]+)\b|[IVXLC]+\.\s|\d+[.)](?!\d)|\(\d+\)|\([a-z]\))"
)


class Chunker:
    def __init__(self, min_chars: int = MIN_CHARS, max_chars: int = MAX_CHARS) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars

    def chunk(self, doc: ParsedDocument) -> list[dict[str, Any]]:
        """Return the list of draft chunks (without doc_id/embedding)."""
        sections = self._build_sections(doc.blocks)
        chunks: list[dict[str, Any]] = []
        for section in sections:
            chunks.extend(self._chunk_section(section))
        # Re-number indexes globally
        for i, c in enumerate(chunks):
            c["chunk_index"] = i
            c["content_hash"] = hashlib.sha256(c["content"].encode("utf-8")).hexdigest()
            c["char_count"] = len(c["content"])
        return chunks

    def _build_sections(self, blocks: list[Block]) -> list[dict[str, Any]]:
        """Assemble blocks into sections by heading hierarchy (with section_path)."""
        sections: list[dict[str, Any]] = []
        current: Optional[dict[str, Any]] = None
        # Heading stack: tracks the heading at each level
        stack: list[str] = []
        for b in blocks:
            if b.type == "heading":
                # Update the heading stack
                while stack and b.level <= len(stack):
                    stack.pop()
                # Start a new section at the current block (the heading itself joins the path)
                while len(stack) < b.level - 1:
                    stack.append("")
                stack.append(b.text)
                current = {"path": list(stack), "title": b.text, "blocks": [], "page": b.page}
                sections.append(current)
            else:
                if current is None:
                    current = {"path": [], "title": "", "blocks": [], "page": b.page}
                    sections.append(current)
                current["blocks"].append(b)
                if b.page is not None and current["page"] is None:
                    current["page"] = b.page
        return sections

    def _chunk_section(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        units = self._split_units(section["blocks"])
        chunks: list[dict[str, Any]] = []
        buf: list[str] = []
        buf_len = 0
        pages: list[int] = []
        has_table = False

        def flush() -> None:
            nonlocal buf, buf_len, has_table
            if not buf:
                return
            content = "\n".join(buf).strip()
            if content:
                chunks.append(
                    {
                        "section_path": section["path"],
                        "section_title": section["title"],
                        "content": content,
                        "char_count": len(content),
                        "metadata": {"page": pages[0] if pages else None, "has_table": has_table},
                    }
                )
            buf = []
            buf_len = 0
            has_table = False

        for unit in units:
            text, page, is_table = unit
            for piece in self._hard_split(text):
                if buf_len + len(piece) > self.max_chars and buf_len >= self.min_chars:
                    flush()
                buf.append(piece)
                buf_len += len(piece)
                if page is not None and not pages:
                    pages.append(page)
                has_table = has_table or is_table
        flush()

        # Merge too-short chunks with the previous one (if either is short)
        return self._merge_short(chunks)

    def _split_units(self, blocks: list[Block]) -> list[tuple[str, Optional[int], bool]]:
        """Split paragraph blocks into minimal semantic units (by clause boundaries)."""
        units: list[tuple[str, Optional[int], bool]] = []
        for b in blocks:
            is_table = b.type == "table"
            if is_table:
                units.append((b.text, b.page, True))
                continue
            lines = [ln.strip() for ln in b.text.splitlines() if ln.strip()]
            for ln in lines:
                # A single paragraph may contain multiple clauses; split by numbering
                parts = self._split_clause_line(ln)
                for p in parts:
                    units.append((p, b.page, False))
        return units

    @staticmethod
    def _split_clause_line(line: str) -> list[str]:
        """Split multiple numbered clauses within one line (conservative: only when numbering appears mid-sentence)."""
        positions = [m.start() for m in CLAUSE_RE.finditer(line)]
        if len(positions) <= 1:
            return [line]
        parts = []
        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(line)
            part = line[pos:end].strip()
            if part:
                parts.append(part)
        # Keep the original line if splitting makes it too fragmented (average < 10 characters)
        if parts and sum(len(p) for p in parts) / len(parts) < 10:
            return [line]
        return parts or [line]

    def _hard_split(self, text: str) -> list[str]:
        """Hard-split units longer than max_chars at sentence boundaries / equal lengths."""
        if len(text) <= self.max_chars:
            return [text]
        pieces: list[str] = []
        buf = ""
        # Prefer splitting at sentence-ending punctuation
        for ch in text:
            buf += ch
            if ch in ".!?;\n" and len(buf) >= self.min_chars:
                pieces.append(buf)
                buf = ""
        if buf:
            pieces.append(buf)
        # Hard-split anything still too long into equal lengths
        final: list[str] = []
        for p in pieces:
            while len(p) > self.max_chars:
                final.append(p[: self.max_chars])
                p = p[self.max_chars :]
            if p:
                final.append(p)
        return final or [text]

    def _merge_short(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for c in chunks:
            if merged and (len(c["content"]) < self.min_chars or len(merged[-1]["content"]) < self.min_chars):
                last = merged[-1]
                last["content"] = (last["content"] + "\n" + c["content"]).strip()
                last["char_count"] = len(last["content"])
                last["metadata"]["has_table"] = last["metadata"].get("has_table") or c["metadata"].get("has_table")
            else:
                merged.append(c)
        return merged
