"""Tests for Issue #14 — unqualified IPC concepts route to the IPC document.

Verifies ``_infer_document_id`` routes criminal concepts (theft, murder, rape,
...) to the Indian Penal Code as ``ipc-concept`` while ICA-domain concepts and
civil terms (consideration, offer, fraud, ...) still resolve to the ICA default,
and that explicit-Act and unique-section queries keep their existing routes.
"""

from __future__ import annotations

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.retrieval.query import parse_query

ICA_DOC_ID = "0d1934142f67c5f5"
IPC_DOC_ID = "cf20a14c52127fd5"


def _build_corpus_graph() -> InMemoryGraph:
    """Canonical dual-Act corpus: ICA + IPC with a few sections each."""
    g = InMemoryGraph()
    g.create_node(
        "Document",
        ICA_DOC_ID,
        {
            "document_id": ICA_DOC_ID,
            "title": "THE INDIAN CONTRACT ACT, 1872",
            "language": "en",
        },
    )
    g.create_node(
        "Document",
        IPC_DOC_ID,
        {
            "document_id": IPC_DOC_ID,
            "title": "THE INDIAN PENAL CODE, 1860",
            "language": "en",
        },
    )
    ica_sections = {"1": "Short title", "10": "What agreements are contracts"}
    ipc_sections = {
        "302": "Punishment for murder",
        "378": "Punishment for theft",
        "415": "Cheating",
        "420": "Cheating and dishonestly inducing delivery of property",
    }
    for num, title in ica_sections.items():
        g.create_node(
            "Section",
            f"ica_sec_{num}",
            {
                "document_id": ICA_DOC_ID,
                "label": "Section",
                "title": title,
                "numbering": num,
                "text": f"Section {num} of the Indian Contract Act.",
            },
        )
    for num, title in ipc_sections.items():
        g.create_node(
            "Section",
            f"ipc_sec_{num}",
            {
                "document_id": IPC_DOC_ID,
                "label": "Section",
                "title": title,
                "numbering": num,
                "text": f"Section {num} of the Indian Penal Code.",
            },
        )
    return g


def _route(query: str) -> tuple[str | None, str]:
    engine = ExplainabilityEngine(_build_corpus_graph())
    return engine._infer_document_id(parse_query(query))


class TestIpcConceptRouting:
    """Unqualified criminal concepts route to the IPC document."""

    def test_theft_routes_to_ipc(self):
        assert _route("What is theft?") == (IPC_DOC_ID, "ipc-concept")

    def test_murder_routes_to_ipc(self):
        assert _route("What is the punishment for murder?") == (
            IPC_DOC_ID,
            "ipc-concept",
        )

    def test_robbery_routes_to_ipc(self):
        assert _route("Explain robbery under the law") == (IPC_DOC_ID, "ipc-concept")

    def test_rape_routes_to_ipc(self):
        assert _route("What is rape?") == (IPC_DOC_ID, "ipc-concept")

    def test_criminal_breach_of_trust_routes_to_ipc(self):
        assert _route("What is criminal breach of trust?") == (
            IPC_DOC_ID,
            "ipc-concept",
        )

    def test_culpable_homicide_routes_to_ipc(self):
        assert _route("Explain culpable homicide not amounting to murder") == (
            IPC_DOC_ID,
            "ipc-concept",
        )

    def test_dowry_death_routes_to_ipc(self):
        assert _route("What is the punishment for dowry death?") == (
            IPC_DOC_ID,
            "ipc-concept",
        )


class TestIcaDefaultRoutingUnchanged:
    """ICA-domain and civil-ambiguous concepts keep the ICA default."""

    def test_consideration_stays_ica(self):
        assert _route("What is consideration?") == (ICA_DOC_ID, "ica-default")

    def test_offer_stays_ica(self):
        assert _route("What is an offer in contract law?") == (ICA_DOC_ID, "ica-default")

    def test_acceptance_stays_ica(self):
        assert _route("Define acceptance") == (ICA_DOC_ID, "ica-default")

    def test_breach_of_contract_stays_ica(self):
        assert _route("What is a breach of contract?") == (ICA_DOC_ID, "ica-default")

    def test_fraud_is_unchanged(self):
        assert _route("What is fraud?") == (ICA_DOC_ID, "ica-default")


class TestExistingRoutingUnchanged:
    """Explicit-Act and unique-section routes are preserved."""

    def test_explicit_act_query_stays_explicit_canonical_act(self):
        assert _route("What is theft under IPC?") == (
            IPC_DOC_ID,
            "explicit-canonical-act",
        )

    def test_unique_section_query_stays_unique_section(self):
        assert _route("What is covered under Section 378?") == (
            IPC_DOC_ID,
            "unique-section",
        )

    def test_word_boundary_does_not_match_substrings(self):
        assert _route("How are grapes classified?") == (ICA_DOC_ID, "ica-default")
        assert _route("What is hurting?") == (ICA_DOC_ID, "ica-default")
