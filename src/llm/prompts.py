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
    "1. Answer strictly from the retrieved sources. Never invent laws, sections, "
    "provisions, or citations that are not present in the evidence.\n"
    "2. Cite every factual claim inline using its bracketed source number, e.g. [1], [2]. "
    "Never cite a source for a claim it does not contain.\n"
    "3. Rely on the hierarchy path and reasoning chain to give structurally aware answers.\n"
    "4. When the question cannot be answered from the evidence, distinguish two cases:\n"
    "   a. NOT IN INDEXED EVIDENCE — the retrieved evidence does not contain the "
    "requested provision or content. State that it is not present in the indexed "
    "evidence and that you cannot confirm or deny it. Do NOT claim it does not exist.\n"
    "   b. TRULY ABSENT — the evidence explicitly enumerates the complete set (e.g. a "
    "table of contents or section index) and the requested provision is not in that "
    "enumeration. Only then state that the provision does not exist, and cite the "
    "enumeration supporting that.\n"
    "5. If the evidence is insufficient, conflicting, or cites an overruled/repealed "
    "authority, say so explicitly and explain WHY the answer cannot be produced with "
    "confidence — name the missing or contradictory pieces of evidence.\n"
    "6. If the user asks in a language other than English, respond in that language.\n\n"
    "Response structure — always answer with exactly these five labelled sections:\n"
    "1. Direct Answer — a concise, direct answer with inline citations.\n"
    "2. Key Points — the main points, each with inline citations.\n"
    "3. Evidence Summary — what the retrieved evidence says on the topic.\n"
    "4. Confidence Explanation — how confident you are and why.\n"
    "5. Limitations — what the evidence does not cover, and whether the question could "
    "not be answered because the information is absent from the indexed evidence."
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
        f"insufficient, state it and explain why. Never invent laws, sections, or "
        f"citations. If the QUESTION asks about a provision or content that is not "
        f"present in the RETRIEVED EVIDENCE, say that it is not in the indexed "
        f"evidence and that you cannot confirm or deny it — do not claim it does not "
        f"exist unless the evidence explicitly enumerates the complete set (e.g. a "
        f"table of contents or section index) that excludes it. Structure your "
        f"answer with the five labelled sections: Direct Answer, Key Points, Evidence "
        f"Summary, Confidence Explanation, Limitations."
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
