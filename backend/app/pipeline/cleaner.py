"""Cleaning and normalization: header/footer/watermark removal, full-width/half-width normalization, Traditional-to-Simplified conversion, whitespace cleanup."""
from __future__ import annotations

import re

from app.pipeline.parser import Block, ParsedDocument


class TextCleaner:
    def __init__(self) -> None:
        # Common header/footer/watermark patterns
        self._noise_patterns = [
            re.compile(r"^\s*page\s*\d+\s*(of|/)\s*\d+\s*$", re.IGNORECASE),
            re.compile(r"^\s*\d+\s*$"),  # Bare page number
            re.compile(r"^\s*(all rights reserved|internal use only|confidential|do not distribute)\.?\s*$", re.IGNORECASE),
        ]

    def clean(self, doc: ParsedDocument) -> ParsedDocument:
        cleaned_blocks: list[Block] = []
        for b in doc.blocks:
            text = self._clean_text(b.text)
            if not text or self._is_noise(text):
                continue
            b.text = text
            cleaned_blocks.append(b)
        doc.blocks = cleaned_blocks
        doc.raw_text = "\n".join(b.text for b in cleaned_blocks)
        return doc

    def clean_text(self, text: str) -> str:
        return self._clean_text(text)

    def _clean_text(self, text: str) -> str:
        text = self._full_to_half(text)
        text = self._traditional_to_simplified(text)
        text = re.sub(r"[ \t\u00a0\u3000]+", " ", text)  # Collapse repeated whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _is_noise(self, text: str) -> bool:
        if len(text) < 2:
            return True
        return any(p.match(text) for p in self._noise_patterns)

    @staticmethod
    def _full_to_half(text: str) -> str:
        out: list[str] = []
        for ch in text:
            code = ord(ch)
            if code == 0x3000:
                out.append(" ")
            elif 0xFF01 <= code <= 0xFF5E:
                out.append(chr(code - 0xFEE0))
            else:
                out.append(ch)
        return "".join(out)

    @staticmethod
    def _traditional_to_simplified(text: str) -> str:
        # Skip Traditional-to-Simplified conversion when opencc is not installed (optional enhancement)
        try:
            from opencc import OpenCC  # Optional dependency

            return OpenCC("t2s").convert(text)
        except ImportError:
            return text
