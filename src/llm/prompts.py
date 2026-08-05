"""Prompt builder — constructs LLM prompts from retrieved evidence.

Evidence blocks carry bracketed source numbers ([1], [2], ...) so the model can
cite sources inline, plus the graph reasoning chain and hierarchy paths for
structure-aware answering.
"""

from __future__ import annotations

from src.llm.provenance import Evidence, ExplanationResult, ReasoningStep

MAX_EVIDENCE_CHARS = 500
MAX_CHAIN_STEPS = 8

SYSTEM_PROMPT = (
    "You are an expert legal analyst for Indian legal documents. You answer questions "
    "using ONLY the retrieved evidence provided by the retrieval system.\n\n"
    "Rules:\n"
    "1. Answer strictly from the retrieved sources. Do not invent laws, sections, or citations.\n"
    "2. Cite every factual claim inline using its bracketed source number, e.g. [1], [2].\n"
    "3. Rely on the hierarchy path and reasoning chain to give structurally aware answers.\n"
    "4. If the evidence is insufficient, conflicting, or cites an overruled/repealed "
    "authority, say so explicitly.\n"
    "5. If the user asks in a language other than English, respond in that language.\n"
    "6. Structure your answer: a direct answer, key points with citations, then a short "
    "note on evidence confidence and caveats."
)


def build_system_prompt(language: str = "en", extra_rules: list[str] | None = None) -> str:
    """Build the system prompt, optionally appending extra rules."""
    prompt = SYSTEM_PROMPT
    if language and language.lower() != "en":
        prompt += f"\n\nThe user is writing in {language} — respond in {language}."
    if extra_rules:
        prompt += "\n" + "\n".join(f"{i}. {rule}" for i, rule in enumerate(extra_rules, 7))
    return prompt


def _display_path(path: list[str]) -> str:
    if not path:
        return "(no hierarchy)"
    return " <- ".join(path)


def format_evidence(evidence: list[Evidence]) -> str:
    """Format evidence into numbered source blocks for the prompt."""
    if not evidence:
        return "(no evidence retrieved)"
    blocks: list[str] = []
    for i, ev in enumerate(evidence, 1):
        numbering = f" | numbering: {ev.numbering}" if ev.numbering else ""
        body = (ev.text or ev.snippet or "").strip().replace("\n", " ")
        if len(body) > MAX_EVIDENCE_CHARS:
            body = body[:MAX_EVIDENCE_CHARS] + "…"
        blocks.append(
            f"[SOURCE {i}] {ev.title} ({ev.label}) — score {ev.final_score:.3f}"
            f"{numbering}\n"
            f"Hierarchy path: {_display_path(ev.path)}\n"
            f"Text: {body}"
        )
    return "\n\n".join(blocks)


def format_reasoning_chain(chain: list[ReasoningStep]) -> str:
    """Format the graph reasoning chain into readable steps."""
    if not chain:
        return "(no reasoning steps recorded)"
    lines: list[str] = []
    for step in chain[:MAX_CHAIN_STEPS]:
        target = f"  nodes: {', '.join(step.node_ids[:6])}" if step.node_ids else ""
        lines.append(f"{step.step}. [{step.kind}] {step.description}{target}")
    return "\n".join(lines)


def build_user_prompt(query: str, explanation: ExplanationResult) -> str:
    """Build the user prompt from a query and its explanation result."""
    evidence = format_evidence(explanation.evidence)
    chain = format_reasoning_chain(explanation.reasoning_chain)

    paths = explanation.hierarchy_paths
    path_lines: list[str] = []
    for p in paths:
        rendered = " <- ".join(e.node_id for e in p.entries)
        path_lines.append(f"  - {p.node_id}: {rendered}")
    hierarchy_block = "\n".join(path_lines) if path_lines else "(no hierarchy paths)"

    return (
        f"QUESTION: {query}\n\n"
        f"RETRIEVED EVIDENCE:\n{evidence}\n\n"
        f"GRAPH REASONING CHAIN:\n{chain}\n\n"
        f"HIERARCHY PATHS:\n{hierarchy_block}\n\n"
        f"INSTRUCTIONS: Answer the QUESTION using only the RETRIEVED EVIDENCE above. "
        f"Cite sources as [1], [2], ... inline. If the evidence conflicts or is "
        f"insufficient, state it and explain why."
    )


def build_messages(
    query: str,
    explanation: ExplanationResult,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    """Build the full message list (system + user) for a chat-completion client."""
    system = system_prompt or build_system_prompt(explanation.query_language)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": build_user_prompt(query, explanation)},
    ]
