"""Environment self-check script (doctor): verifies that DeepSeek and the relay service (non-DeepSeek models such as bge) can be called successfully.

Usage:
    cd backend
    python -m scripts.doctor          # Use the keys from .env / environment variables
    python -m scripts.doctor --json   # Output JSON results (for CI / frontend display)

Checks:
    1. DeepSeek chat model (default deepseek-v4-flash)
    2. Relay service chat model (default gpt-5.5-pro, OpenAI-compatible)
    3. Relay service Embedding model (default bge-m3, /embeddings)

Exit code: 0 if everything passes, 1 if anything fails.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Default config (consistent with .env; model names verified to work by doctor)
DEFAULT_DEEPSEEK_BASE = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_RELAY_BASE = "https://yunwu.ai/v1"
DEFAULT_RELAY_MODEL = "gpt-5.5"                     # Relay service chat model (gpt-5.5-pro is invalid)
DEFAULT_EMBED_MODEL = "text-embedding-3-large"       # Relay service Embedding (bge-m3 is unavailable on this relay)
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"     # Relay service bge reranker model (bge family)


def _load_env() -> None:
    """Load program/.env or backend/.env (without overriding existing environment variables)."""
    candidates = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",          # Read program/.env when running from backend/
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        return


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


async def check_chat(base_url: str, api_key: str, model: str, name: str, timeout: float = 30.0) -> dict[str, Any]:
    """Check the chat model /chat/completions."""
    started = time.perf_counter()
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Introduce yourself in one sentence."}],
        "temperature": 0.1,
        "max_tokens": 64,
        "stream": False,
    }
    result = {"name": name, "kind": "chat", "model": model, "url": url, "ok": False}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=_headers(api_key), json=payload)
        latency = round((time.perf_counter() - started) * 1000, 1)
        result["latency_ms"] = latency
        result["status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result["ok"] = True
            result["sample"] = content[:120]
        else:
            result["error"] = resp.text[:500]
    except httpx.HTTPError as exc:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


async def check_embedding(base_url: str, api_key: str, model: str, name: str, timeout: float = 30.0) -> dict[str, Any]:
    """Check the Embedding model /embeddings (bge-m3, etc.)."""
    started = time.perf_counter()
    url = base_url.rstrip("/") + "/embeddings"
    payload = {"model": model, "input": ["cross-department document Q&A assistant"]}
    result = {"name": name, "kind": "embedding", "model": model, "url": url, "ok": False}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=_headers(api_key), json=payload)
        latency = round((time.perf_counter() - started) * 1000, 1)
        result["latency_ms"] = latency
        result["status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            vec = data["data"][0]["embedding"]
            result["ok"] = True
            result["dim"] = len(vec)
            result["sample"] = f"dim={len(vec)}, head={vec[:3]}"
        else:
            result["error"] = resp.text[:500]
    except httpx.HTTPError as exc:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


async def check_rerank(base_url: str, api_key: str, model: str, name: str, timeout: float = 30.0) -> dict[str, Any]:
    """Check the bge reranker model /rerank."""
    started = time.perf_counter()
    url = base_url.rstrip("/") + "/rerank"
    payload = {
        "model": model,
        "query": "course registration period",
        "documents": ["Course registration takes place in weeks 16 to 18", "Tuition is paid before the semester starts"],
    }
    result = {"name": name, "kind": "rerank", "model": model, "url": url, "ok": False}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=_headers(api_key), json=payload)
        latency = round((time.perf_counter() - started) * 1000, 1)
        result["latency_ms"] = latency
        result["status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            scores = [r["relevance_score"] for r in data.get("results", [])]
            result["ok"] = True
            result["sample"] = f"top scores={[round(s, 4) for s in scores[:3]]}"
        else:
            result["error"] = resp.text[:500]
    except httpx.HTTPError as exc:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


async def run_all() -> list[dict[str, Any]]:
    _load_env()
    deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE)
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    relay_base = os.environ.get("RELAY_BASE_URL", DEFAULT_RELAY_BASE)
    relay_key = os.environ.get("RELAY_API_KEY", "")
    relay_model = os.environ.get("RELAY_MODEL", DEFAULT_RELAY_MODEL)
    embed_model = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBED_MODEL)
    rerank_model = os.environ.get("RERANKER_MODEL", DEFAULT_RERANK_MODEL)

    results = []
    results.append(await check_chat(deepseek_base, deepseek_key, deepseek_model, "DeepSeek chat"))
    results.append(await check_chat(relay_base, relay_key, relay_model, "Relay chat"))
    results.append(await check_embedding(relay_base, relay_key, embed_model, "Relay Embedding"))
    results.append(await check_rerank(relay_base, relay_key, rerank_model, "Relay bge rerank"))
    return results


def _print_report(results: list[dict[str, Any]]) -> None:
    print("=" * 66)
    print("Clausewise · Model connectivity self-check (doctor)")
    print("=" * 66)
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"[{mark}] {r['name']:24s} model={r['model']:20s} "
              f"status={r.get('status', '-')} latency={r.get('latency_ms', '-')}ms")
        if r["ok"]:
            print(f"       sample: {r.get('sample', '')}")
        else:
            print(f"       error : {r.get('error', '')[:200]}")
    all_ok = all(r["ok"] for r in results)
    print("-" * 66)
    print("Result:", "all passed ✅" if all_ok else "some checks failed ❌")
    print("=" * 66)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Clausewise model connectivity self-check")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    results = await run_all()
    if args.json:
        print(json.dumps({"results": results, "all_ok": all(r["ok"] for r in results)}, ensure_ascii=False, indent=2))
    else:
        _print_report(results)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
