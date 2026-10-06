"""Root pytest config: force offline mode (memory storage + hash vectors) so tests need no external services."""
from __future__ import annotations

import os
import sys

# Make app importable from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Must be set before importing app
os.environ.setdefault("STORAGE_MODE", "memory")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("EMBEDDING_DIM", "128")
os.environ.setdefault("LOOP_ENABLED", "true")
os.environ.setdefault("LOOP_PHASE", "human_on_loop")
os.environ.setdefault("PI_AGENT_ENABLED", "false")
os.environ.setdefault("RERANKER_ENABLED", "false")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("RELAY_API_KEY", "")
