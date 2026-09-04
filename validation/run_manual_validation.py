"""End-to-end manual validation runner for the HHGR legal QA system.

EXERCISES THE FULL PIPELINE EXACTLY AS A USER WOULD:

    POST /query  ->  retrieval -> ranking -> relevance -> sufficiency ->
                    confidence -> verification badge -> grounding guard -> LLM

Not a unit test. Each case is a full request routed through the FastAPI app.
The runner builds the real in-memory corpus (data/hierarchy) once and injects a
deterministic mock LLM so the whole run is reproducible offline.

Usage:
    python validation/run_manual_validation.py

Outputs:
    validation/validation_report.md
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

VALIDATION_DIR = Path(__file__).resolve().parent
CASES_PATH = VALIDATION_DIR / "expected_results.json"
REPORT_PATH = VALIDATION_DIR / "validation_report.md"

# Canonical document slugs used when labelling the top retrieved document.
DOC_SLUGS = {
    "0d1934142f67c5f5": "ICA (Contract Act)",
    "cf20a14c52127fd5": "IPC (Penal Code)",
}

BLOCKED_ANSWER = (
    "I could not verify this answer from the indexed legal corpus. "
    "The retrieved evidence is insufficient to provide a reliable legal response."
)


def _doc_slug(node_id: str) -> tuple[str, str]:
    """Return (doc_id, slug) from a namespaced node id like {doc}__{node}."""
    doc_id = node_id.split("__", 1)[0] if node_id else ""
    return doc_id, DOC_SLUGS.get(doc_id, node_id[:12])


def build_service():
    """Build the default service over the real corpus with a mock LLM."""
    from src.config.settings import settings
    from src.embeddings import VectorRetriever
    from src.llm import service as svc_mod
    from src.llm.explanation import ExplainabilityEngine
    from src.llm.llm import MockLLMClient
    from src.llm.provenance import ProvenanceStore
    from src.llm.service import QueryService

    settings.LLM_PROVIDER = "mock"
    graph, store, embedding = svc_mod.get_default_corpus()
    vector_retriever = VectorRetriever(graph, store, embedding)
    engine = ExplainabilityEngine(
        graph,
        vector_retriever=vector_retriever,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )
    engine.llm_client = MockLLMClient()
    return QueryService(
        engine,
        MockLLMClient(),
        ProvenanceStore(),
        top_k=settings.QA_TOP_K,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )


def run_case(client, case: dict) -> dict:
    """POST /query for a single case and normalise the response."""
    payload = {"query": case["query"], "top_k": 5}
    t0 = time.perf_counter()
    try:
        resp = client.post("/api/v1/query", json=payload)
    except Exception as exc:  # server-side unhandled error leaking to client
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": False,
            "error": f"raised {type(exc).__name__}: {str(exc)[:200]}",
            "status": "error",
            "confidence": 0.0,
            "duration_ms": duration_ms,
            "evidence": [],
            "blocked": False,
            "top_section": "",
            "top_doc": "",
        }
    duration_ms = (time.perf_counter() - t0) * 1000.0

    if resp.status_code != 200:
        return {
            "ok": False,
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            "status": "error",
            "confidence": 0.0,
            "duration_ms": duration_ms,
            "evidence": [],
            "blocked": False,
            "top_section": "",
            "top_doc": "",
        }

    data = resp.json()
    evidence = data.get("evidence") or []
    top = evidence[0] if evidence else {}
    node_id = top.get("node_id", "")
    doc_id, doc_slug = _doc_slug(node_id)
    answer = data.get("answer", "")
    return {
        "ok": True,
        "status": (data.get("validity") or {}).get("status"),
        "confidence": (data.get("confidence") or {}).get("score", 0.0),
        "sufficiency": (data.get("validity") or {}).get("sufficiency_score", 0.0),
        "relevance": (data.get("validity") or {}).get("relevance_score", 0.0),
        "duration_ms": data.get("duration_ms", duration_ms),
        "evidence": evidence,
        "blocked": (answer == BLOCKED_ANSWER),
        "blocked_model": (data.get("model") == "grounding-guard"),
        "top_section": str(top.get("numbering", "")).strip(),
        "top_doc": doc_slug,
        "top_doc_id": doc_id,
        "answer_len": len(answer),
    }


def evaluate(case_id: str, case: dict, actual: dict) -> dict:
    """Compare one live response against its expectations."""
    exp_status = case["expected_status"]
    exp_section = case["expected_section"]
    exp_blocked = case["blocked"]
    checks = {}

    checks["status"] = actual["status"] == exp_status
    checks["blocked"] = actual["blocked"] == exp_blocked

    if exp_section == "none":
        checks["section"] = True  # no section expected; blocked case
    else:
        checks["section"] = actual["top_section"] == exp_section

    conf = actual["confidence"]
    checks["confidence"] = case["confidence_min"] <= conf <= case["confidence_max"]

    passed = all(checks.values()) and actual["ok"]
    return {"case_id": case_id, "passed": passed, "checks": checks, "actual": actual}


def top_failure_patterns(failures: list[dict]) -> list[str]:
    """Group the top failure reasons into a short ordered list."""
    reasons = Counter()
    for f in failures:
        c = f["checks"]
        if not c["status"]:
            reasons["verification status mismatch"] += 1
        if not c["section"]:
            reasons["wrong/absent top section"] += 1
        if not c["blocked"]:
            reasons["grounding-guard block mismatch"] += 1
        if not c.get("confidence", True):
            reasons["confidence out of range"] += 1
        if not f["actual"].get("ok"):
            reasons["request failed"] += 1
    return [f"{n}x {reason}" for reason, n in reasons.most_common(6)]


def write_report(
    categories: dict[str, list[dict]],
    totals: dict,
) -> None:
    lines = []
    lines.append("# HHGR Legal QA — Manual Validation Report")
    lines.append("")
    lines.append("End-to-end run against the local `/query` pipeline (deterministic mock LLM).")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total queries | {totals['total']} |")
    lines.append(f"| Pass | {totals['pass']} |")
    lines.append(f"| Fail | {totals['fail']} |")
    lines.append(f"| Pass rate | {totals['pass_rate']:.1f}% |")
    lines.append(f"| Average confidence | {totals['avg_confidence']:.3f} |")
    lines.append(f"| Average latency | {totals['avg_latency']:.1f} ms |")
    lines.append(f"| Wrong-document retrievals | {totals['wrong_doc']} |")
    lines.append(f"| Hallucinations prevented | {totals['hallucinations_prevented']} |")
    lines.append(f"| Grounding-guard activations | {totals['guard_activations']} |")
    lines.append("")
    lines.append("## By category")
    lines.append("")
    lines.append("| Category | Cases | Pass | Fail | Pass rate | Avg conf | Avg ms |")
    lines.append("|----------|-------|------|------|-----------|----------|--------|")
    for name, results in categories.items():
        n = len(results)
        p = sum(1 for r in results if r["passed"])
        avg_conf = sum(r["actual"]["confidence"] for r in results) / n if n else 0
        avg_ms = sum(r["actual"]["duration_ms"] for r in results) / n if n else 0
        lines.append(
            f"| {name} | {n} | {p} | {n-p} | {p/n*100:.1f}% | "
            f"{avg_conf:.3f} | {avg_ms:.1f} |"
        )
    lines.append("")
    lines.append("## Top failure patterns")
    lines.append("")
    if totals["patterns"]:
        for pat in totals["patterns"]:
            lines.append(f"- {pat}")
    else:
        lines.append("- None — every case passed.")
    lines.append("")
    lines.append("## Per-case results")
    lines.append("")
    lines.append("| Case | Status | Conf | Blocked | Top section | Top doc | Result |")
    lines.append("|------|--------|------|---------|-------------|---------|--------|")
    for name, results in categories.items():
        for r in results:
            a = r["actual"]
            lines.append(
                f"| {r['case_id']} | {a.get('status') or '-':<12} | "
                f"{a['confidence']:.3f} | {str(a['blocked']):<5} | "
                f"{(a['top_section'] or '-')[:16]:<16} | {a['top_doc'] or '-':<20} | "
                f"{'PASS' if r['passed'] else 'FAIL'} |"
            )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")


def main() -> None:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases: dict[str, dict] = data["cases"]

    from fastapi.testclient import TestClient

    from src.api import qa
    from src.main import app

    print("Building default service and corpus (first run indexes in-memory)...")
    _service = build_service()
    qa.service_factory = lambda: _service

    categories = defaultdict(list)
    with TestClient(app) as client:
        for case_id, case in cases.items():
            actual = run_case(client, case)
            result = evaluate(case_id, case, actual)
            cat = case_id.split(".")[0]
            categories[f"Category {cat}"].append(result)
            print(f"[{case_id}] status={actual.get('status')} "
                  f"conf={actual['confidence']:.3f} blocked={actual['blocked']} "
                  f"sec={actual['top_section']!r} doc={actual['top_doc']} "
                  f"-> {'PASS' if result['passed'] else 'FAIL'}")

    all_results = [r for res in categories.values() for r in res]
    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    wrong_doc = sum(
        1 for r in all_results
        if r["actual"]["ok"]
        and r["case_id"][0] not in ("5", "6")
        and r["actual"]["top_doc_id"] not in ("0d1934142f67c5f5",)
    )
    hallucinations_prevented = sum(
        1 for r in all_results
        if r["case_id"][0] in ("5", "6") and r["actual"]["blocked"]
    )
    guard_activations = sum(1 for r in all_results if r["actual"]["blocked"])
    avg_conf = sum(r["actual"]["confidence"] for r in all_results) / total if total else 0
    avg_lat = sum(r["actual"]["duration_ms"] for r in all_results) / total if total else 0
    failures = [r for r in all_results if not r["passed"]]

    totals = {
        "total": total,
        "pass": passed,
        "fail": total - passed,
        "pass_rate": passed / total * 100 if total else 0,
        "avg_confidence": avg_conf,
        "avg_latency": avg_lat,
        "wrong_doc": wrong_doc,
        "hallucinations_prevented": hallucinations_prevented,
        "guard_activations": guard_activations,
        "patterns": top_failure_patterns(failures),
    }
    write_report(categories, totals)


if __name__ == "__main__":
    main()
