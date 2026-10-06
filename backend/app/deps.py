"""Dependency wiring: builds the global singleton container (LLM / storage / retrieval / agents / Loop)."""
from __future__ import annotations
from typing import Optional

from dataclasses import dataclass

from app.auth import AuthService
from app.config import Settings, get_settings
from app.harness.agents.answer_agent import AnswerAgent
from app.harness.agents.dept_router import DeptRouter
from app.harness.agents.feedback_agent import FeedbackAgent
from app.harness.agents.intent_agent import IntentAgent
from app.harness.agents.query_rewriter import QueryRewriter
from app.harness.agents.retrieval_agent import RetrievalAgent
from app.harness.agents.verifier_agent import VerifierAgent
from app.harness.orchestrator import Orchestrator
from app.integrations.pi_client import PiAgentClient
from app.integrations.dept_agent_client import DepartmentAgentClient
from app.integrations.pi_runtime import PiAgentRuntimeClient
from app.llm.deepseek import DeepSeekClient
from app.llm.embeddings import EmbeddingClient
from app.llm.relay import RelayClient
from app.loop.feedback_collector import FeedbackCollector
from app.loop.hook_engine import HookEngine
from app.loop.loop_engine import LoopEngine
from app.loop.rule_engine import RuleEngine
from app.loop.skill_miner import SkillMiner
from app.loop.skill_executor import SkillExecutor
from app.loop.strategy_evaluator import StrategyEvaluator
from app.memory.department import DepartmentMemory
from app.memory.global_memory import GlobalMemory
from app.memory.user import UserMemory
from app.memory.working import WorkingMemory
from app.memory.episodic import EpisodicMemory
from app.memory.user_semantic import UserSemanticMemory
from app.memory.organization import OrganizationMemory
from app.memory.learning import LearningMemory
from app.memory.context_builder import MemoryContextBuilder
from app.memory.facts import FactPlane
from app.memory.retention import MemoryRetentionManager
from app.pipeline.conflict_detector import ConflictDetector
from app.pipeline.indexer import Indexer
from app.retrieval.bm25 import BM25Index, SharedBM25Index
from app.review.review_engine import ReviewEngine
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import build_reranker
from app.retrieval.vector_store import build_vector_store
from app.storage.mongodb import MongoDB
from app.storage.redis_store import build_session_store
from app.storage.store import build_store
from app.storage.job_queue import JobQueue
from app.utils.logging import get_logger
from app.utils.ratelimit import MemoryRateLimiter

logger = get_logger(__name__)


@dataclass
class Container:
    settings: Settings
    store: object
    session_store: object
    mongo: Optional[MongoDB]
    bm25: BM25Index
    vector_store: object
    llm: DeepSeekClient
    relay: RelayClient
    embeddings: EmbeddingClient
    indexer: Indexer
    conflict_detector: ConflictDetector
    retrieval_agent: RetrievalAgent
    working_memory: WorkingMemory
    user_memory: UserMemory
    dept_memory: DepartmentMemory
    global_memory: GlobalMemory
    episodic_memory: EpisodicMemory
    user_semantic_memory: UserSemanticMemory
    organization_memory: OrganizationMemory
    learning_memory: LearningMemory
    memory_context_builder: MemoryContextBuilder
    fact_plane: FactPlane
    memory_retention: MemoryRetentionManager
    orchestrator: Orchestrator
    pi_client: PiAgentClient
    dept_agent_client: DepartmentAgentClient
    pi_runtime: PiAgentRuntimeClient
    loop_engine: LoopEngine
    feedback_collector: FeedbackCollector
    hook_engine: HookEngine
    rule_engine: RuleEngine
    skill_miner: SkillMiner
    skill_executor: SkillExecutor
    strategy_evaluator: StrategyEvaluator
    feedback_agent: FeedbackAgent
    dept_router: DeptRouter
    auth: AuthService
    review_engine: ReviewEngine
    login_limiter: MemoryRateLimiter
    job_queue: JobQueue


def build_container(settings: Optional[Settings] = None) -> Container:
    settings = settings or get_settings()

    mongo = MongoDB(settings)
    store = build_store(mongo)
    session_store = build_session_store(settings)
    job_queue = JobQueue(store, session_store, settings.async_stream_name)

    llm = DeepSeekClient(settings)
    relay = RelayClient(settings)
    embeddings = EmbeddingClient(settings, relay)
    pi_runtime = PiAgentRuntimeClient(settings)

    vector_store = build_vector_store(settings.vector_backend, store)
    bm25 = SharedBM25Index(store) if settings.vector_backend == "mongo" else BM25Index()
    reranker = build_reranker(settings.reranker_enabled, settings.reranker_model, relay=relay)
    hybrid = HybridRetriever(
        bm25=bm25,
        vector_store=vector_store,
        reranker=reranker,
        bm25_top=settings.bm25_top,
        vector_top=settings.vector_top,
        top_k=settings.hybrid_topk,
    )

    indexer = Indexer(store=store, vector_store=vector_store, embeddings=embeddings, bm25=bm25, llm=llm)
    conflict_detector = ConflictDetector(store=store, vector_store=vector_store, embeddings=embeddings, llm=llm)

    working_memory = WorkingMemory(
        session_store, ttl=settings.memory_session_ttl_seconds, max_history=settings.memory_max_recent_messages
    )
    user_memory = UserMemory(store)
    dept_memory = DepartmentMemory(store, settings.memory_topic_retention_days)
    global_memory = GlobalMemory(store)
    episodic_memory = EpisodicMemory(
        store, settings.memory_event_retention_days, settings.memory_summary_retention_days
    )
    user_semantic_memory = UserSemanticMemory(store, settings.memory_user_retention_days)
    organization_memory = OrganizationMemory(store)
    indexer.organization_memory = organization_memory
    learning_memory = LearningMemory(store)
    fact_plane = FactPlane(store)
    memory_retention = MemoryRetentionManager(store)
    memory_context_builder = MemoryContextBuilder(
        store, working_memory, episodic_memory, user_semantic_memory, organization_memory, learning_memory,
        max_chars=settings.memory_context_max_chars, user_limit=settings.memory_user_limit,
        org_limit=settings.memory_org_limit, recent_limit=settings.memory_max_recent_messages,
    )

    intent_agent = IntentAgent(llm, store, pi_runtime, settings.pi_runtime_timeout_intent)
    dept_router = DeptRouter(llm, store)
    query_rewriter = QueryRewriter(llm, store, pi_runtime, settings.pi_runtime_timeout_rewrite)
    retrieval_agent = RetrievalAgent(hybrid, embeddings, store)
    answer_agent = AnswerAgent(llm, store, pi_runtime, settings.pi_runtime_timeout_answer)
    verifier_agent = VerifierAgent(llm, pi_runtime, settings.pi_runtime_timeout_verify)
    feedback_agent = FeedbackAgent(store)

    rule_engine = RuleEngine(store)
    hook_engine = HookEngine(store)
    skill_miner = SkillMiner(store, llm, min_cluster=settings.skill_min_cluster)
    skill_executor = SkillExecutor(store, default_top_k=settings.hybrid_topk)
    feedback_collector = FeedbackCollector(store)
    pi_client = PiAgentClient(settings)
    dept_agent_client = DepartmentAgentClient(settings)

    auth = AuthService(store, settings)
    login_limiter = MemoryRateLimiter(
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
    )
    review_engine = ReviewEngine(
        settings=settings,
        store=store,
        llm=llm,
        retrieval_agent=retrieval_agent,
        answer_agent=answer_agent,
        rule_engine=rule_engine,
        feedback_collector=feedback_collector,
    )
    strategy_evaluator = StrategyEvaluator(
        retrieval_agent, answer_agent, verifier_agent, rule_engine, skill_executor
    )

    loop_engine = LoopEngine(
        settings=settings,
        store=store,
        llm=llm,
        embeddings=embeddings,
        skill_miner=skill_miner,
        hook_engine=hook_engine,
        rule_engine=rule_engine,
        feedback_collector=feedback_collector,
        strategy_evaluator=strategy_evaluator,
        pi_runtime=pi_runtime,
    )

    orchestrator = Orchestrator(
        settings=settings,
        store=store,
        working_memory=working_memory,
        user_memory=user_memory,
        dept_memory=dept_memory,
        episodic_memory=episodic_memory,
        memory_context_builder=memory_context_builder,
        organization_memory=organization_memory,
        intent_agent=intent_agent,
        dept_router=dept_router,
        query_rewriter=query_rewriter,
        retrieval_agent=retrieval_agent,
        answer_agent=answer_agent,
        verifier_agent=verifier_agent,
        feedback_agent=feedback_agent,
        loop_engine=loop_engine,
        hook_engine=hook_engine,
        rule_engine=rule_engine,
        skill_executor=skill_executor,
        dept_agent_client=dept_agent_client,
        pi_client=pi_client,
    )

    return Container(
        settings=settings,
        store=store,
        session_store=session_store,
        mongo=mongo,
        bm25=bm25,
        vector_store=vector_store,
        llm=llm,
        relay=relay,
        embeddings=embeddings,
        indexer=indexer,
        conflict_detector=conflict_detector,
        retrieval_agent=retrieval_agent,
        working_memory=working_memory,
        user_memory=user_memory,
        dept_memory=dept_memory,
        global_memory=global_memory,
        episodic_memory=episodic_memory,
        user_semantic_memory=user_semantic_memory,
        organization_memory=organization_memory,
        learning_memory=learning_memory,
        memory_context_builder=memory_context_builder,
        fact_plane=fact_plane,
        memory_retention=memory_retention,
        orchestrator=orchestrator,
        pi_client=pi_client,
        dept_agent_client=dept_agent_client,
        pi_runtime=pi_runtime,
        loop_engine=loop_engine,
        feedback_collector=feedback_collector,
        hook_engine=hook_engine,
        rule_engine=rule_engine,
        skill_miner=skill_miner,
        skill_executor=skill_executor,
        strategy_evaluator=strategy_evaluator,
        feedback_agent=feedback_agent,
        dept_router=dept_router,
        auth=auth,
        review_engine=review_engine,
        login_limiter=login_limiter,
        job_queue=job_queue,
    )
