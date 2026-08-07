"""Module 7 — Explainable LLM Answer Generation.

Retrieval provenance, prompt building, explainability, and LLM answer generation
over the HHGR / vector retrieval layers.
"""

from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import (
    GeminiClient,
    LlamaClient,
    LLMClient,
    LLMError,
    LLMResponse,
    MistralClient,
    MockLLMClient,
    OpenAICompatClient,
    QwenClient,
    get_llm_client,
)
from src.llm.prompts import (
    SYSTEM_PROMPT,
    build_messages,
    build_system_prompt,
    build_user_prompt,
    format_evidence,
    format_reasoning_chain,
)
from src.llm.provenance import (
    AnswerResult,
    Confidence,
    CounterAuthority,
    Evidence,
    ExplanationResult,
    HierarchyPath,
    HierarchyPathEntry,
    ProvenanceStore,
    ReasoningStep,
    RetrievalSummary,
    SourceCitation,
    Validity,
)
from src.llm.service import (
    QueryService,
    build_default_corpus,
    build_default_graph,
    build_default_service,
    get_default_corpus,
    get_default_service,
)

__all__ = [
    "ExplainabilityEngine",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "OpenAICompatClient",
    "GeminiClient",
    "LlamaClient",
    "MistralClient",
    "QwenClient",
    "MockLLMClient",
    "get_llm_client",
    "SYSTEM_PROMPT",
    "build_messages",
    "build_system_prompt",
    "build_user_prompt",
    "format_evidence",
    "format_reasoning_chain",
    "AnswerResult",
    "Evidence",
    "ExplanationResult",
    "ReasoningStep",
    "HierarchyPath",
    "HierarchyPathEntry",
    "SourceCitation",
    "CounterAuthority",
    "Confidence",
    "Validity",
    "RetrievalSummary",
    "ProvenanceStore",
    "QueryService",
    "build_default_corpus",
    "build_default_graph",
    "build_default_service",
    "get_default_corpus",
    "get_default_service",
]
