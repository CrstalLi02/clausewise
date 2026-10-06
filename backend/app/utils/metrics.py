"""Prometheus metrics: Q&A latency, retrieval hit rate, adoption rate, cost, etc."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

QUERY_TOTAL = Counter("clausewise_query_total", "Total number of Q&A requests", ["dept", "intent"])
QUERY_LATENCY = Histogram("clausewise_query_latency_seconds", "End-to-end Q&A latency", ["dept"])
LLM_LATENCY = Histogram("clausewise_llm_latency_seconds", "LLM call latency", ["model"])
RETRIEVAL_HIT = Counter("clausewise_retrieval_hit_total", "Retrieval hit count", ["dept"])
RETRIEVAL_MISS = Counter("clausewise_retrieval_miss_total", "Retrieval miss count", ["dept"])
ADOPTION = Counter("clausewise_answer_adoption_total", "Answer adoption/thumbs-down count", ["kind"])  # kind: up/down
LLM_COST = Gauge("clausewise_llm_cost_yuan", "Cumulative LLM cost (CNY)")
FEEDBACK_TOTAL = Counter("clausewise_feedback_total", "Total feedback count", ["kind"])
SKILL_TRIGGER = Counter("clausewise_skill_trigger_total", "Skill trigger count", ["skill"])
DEPT_AGENT_REQUEST = Counter("clausewise_dept_agent_requests_total", "Department agent request count", ["dept", "status"])
DEPT_AGENT_INFLIGHT = Gauge("clausewise_dept_agent_inflight", "Department agent current in-flight requests", ["dept"])
PI_AGENT_EXECUTION = Counter("clausewise_pi_agent_execution_total", "pi agent execution count", ["agent", "status"])


def record_retrieval_hit(dept: str, hit: bool) -> None:
    (RETRIEVAL_HIT if hit else RETRIEVAL_MISS).labels(dept=dept).inc()


def record_adoption(kind: str) -> None:
    ADOPTION.labels(kind=kind).inc()
