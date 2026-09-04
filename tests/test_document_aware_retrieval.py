"""Tests for document-aware retrieval — Task 13 regression tests.

Verifies that queries scoped to a specific Act only retrieve evidence from
that Act's document, and that cross-document citation contamination is blocked.
"""

from __future__ import annotations

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.retrieval.query import parse_query
from src.retrieval.ranker import retrieve
from src.retrieval.scorer import citation_score

ICA_DOC_ID = "0d1934142f67c5f5"
IPC_DOC_ID = "cf20a14c52127fd5"


class TestParseQueryDocumentId:
    """Phase 2: parse_query extracts act_name and resolves document_id."""

    def test_ica_act_resolves_to_document_id(self):
        q = parse_query("What is Section 10 of the Indian Contract Act?")
        assert q.act_name == "the Indian Contract Act"
        assert q.document_id == ICA_DOC_ID

    def test_ipc_act_resolves_to_document_id(self):
        q = parse_query("What is Section 302 of the Indian Penal Code?")
        assert q.act_name == "the Indian Penal Code"
        assert q.document_id == IPC_DOC_ID

    def test_short_act_name_resolves(self):
        q = parse_query("Section 23 under Contract Act")
        assert q.document_id == ICA_DOC_ID

    def test_no_act_name_leaves_document_id_empty(self):
        q = parse_query("What is consideration in contract law?")
        assert q.act_name == ""
        assert q.document_id == ""

    def test_ica_1872_resolves(self):
        q = parse_query("Section 75 of the Indian Contract Act, 1872")
        assert q.document_id == ICA_DOC_ID

    def test_ipc_1860_resolves(self):
        q = parse_query("Section 498A of the Indian Penal Code, 1860")
        assert q.document_id == IPC_DOC_ID


class TestCitationScoreDocumentScoped:
    """Phase 5: citation_score blocks cross-document matches."""

    def _ica_node(self, numbering: str = "10", **kw):
        node = {
            "node_id": "ica_sec_10",
            "label": "Section",
            "title": "What agreements are contracts",
            "text": "Section 10 of the Indian Contract Act",
            "numbering": numbering,
            "document_id": ICA_DOC_ID,
        }
        node.update(kw)
        return node

    def _ipc_node(self, numbering: str = "302", **kw):
        node = {
            "node_id": "ipc_sec_302",
            "label": "Section",
            "title": "Punishment for murder",
            "text": "Whoever commits murder shall be punished",
            "numbering": numbering,
            "document_id": IPC_DOC_ID,
        }
        node.update(kw)
        return node

    def test_scoped_ica_matches_ica_node(self):
        q = parse_query("Section 10 of the Indian Contract Act")
        assert citation_score(self._ica_node(), q) == 1.0

    def test_scoped_ica_blocks_ipc_node(self):
        q = parse_query("Section 10 of the Indian Contract Act")
        # IPC node with numbering "10" should NOT match
        ipc_node_10 = self._ipc_node(numbering="10")
        assert citation_score(ipc_node_10, q) == 0.0

    def test_scoped_ipc_matches_ipc_node(self):
        q = parse_query("Section 302 of the Indian Penal Code")
        assert citation_score(self._ipc_node(), q) == 1.0

    def test_scoped_ipc_blocks_ica_node(self):
        q = parse_query("Section 302 of the Indian Penal Code")
        assert citation_score(self._ica_node(numbering="302"), q) == 0.0

    def test_unscoped_matches_any_document(self):
        q = parse_query("Section 10")
        assert citation_score(self._ica_node(), q) == 1.0
        ipc_node_10 = self._ipc_node(numbering="10")
        assert citation_score(ipc_node_10, q) == 1.0

    def test_no_node_document_id_passes_through(self):
        """When the node lacks document_id, the citation is not blocked."""
        q = parse_query("Section 10 of the Indian Contract Act")
        node_no_doc = {
            "node_id": "unknown",
            "label": "Section",
            "title": "Some section",
            "text": "Some text",
            "numbering": "10",
        }
        assert citation_score(node_no_doc, q) == 1.0


class TestGraphRetrievalDocumentScoped:
    """Phase 4: graph retrieve() filters candidates by document_id."""

    def _build_graph(self):
        graph = InMemoryGraph()
        # ICA document
        graph.create_node("Document", ICA_DOC_ID, {
            "document_id": ICA_DOC_ID, "title": "Indian Contract Act",
        })
        graph.create_node("Section", "ica_sec_10", {
            "node_id": "ica_sec_10", "document_id": ICA_DOC_ID,
            "title": "What agreements are contracts",
            "text": "All agreements are contracts if made by free consent",
            "numbering": "10",
            "hierarchy_level": 2,
        })
        graph.create_edge("ica_sec_10", ICA_DOC_ID, "PART_OF")
        graph.create_node("Section", "ica_sec_23", {
            "node_id": "ica_sec_23", "document_id": ICA_DOC_ID,
            "title": "What is consideration",
            "text": "When at the desire of the promisor, the promisee has done",
            "numbering": "23",
            "hierarchy_level": 2,
        })
        graph.create_edge("ica_sec_23", ICA_DOC_ID, "PART_OF")

        # IPC document
        graph.create_node("Document", IPC_DOC_ID, {
            "document_id": IPC_DOC_ID, "title": "Indian Penal Code",
        })
        graph.create_node("Section", "ipc_sec_302", {
            "node_id": "ipc_sec_302", "document_id": IPC_DOC_ID,
            "title": "Punishment for murder",
            "text": "Whoever commits murder shall be punished with death",
            "numbering": "302",
            "hierarchy_level": 2,
        })
        graph.create_edge("ipc_sec_302", IPC_DOC_ID, "PART_OF")
        return graph

    def test_scoped_query_returns_only_ica_nodes(self):
        graph = self._build_graph()
        results = retrieve(
            graph, "What is Section 10 of the Indian Contract Act?",
            top_k=10, document_id=ICA_DOC_ID,
        )
        node_ids = [r.node_id for r in results]
        assert "ica_sec_10" in node_ids
        assert "ipc_sec_302" not in node_ids

    def test_unscoped_query_returns_all_nodes(self):
        graph = self._build_graph()
        results = retrieve(
            graph, "What is Section 10?",
            top_k=10, document_id=None,
        )
        node_ids = [r.node_id for r in results]
        assert "ica_sec_10" in node_ids

    def test_empty_document_id_returns_all_nodes(self):
        graph = self._build_graph()
        results = retrieve(
            graph, "Section 10 of the Indian Contract Act",
            top_k=10, document_id="",
        )
        node_ids = [r.node_id for r in results]
        # Should find at least one node (unscoped fallback)
        assert len(node_ids) > 0


class TestQdrantDocumentFilter:
    """Phase 3: QdrantStore.search() filters by doc_id payload."""

    def test_search_with_document_id(self):
        from src.embeddings.store import QdrantStore

        store = QdrantStore(dim=384, in_memory=True)
        store.ensure_collections()
        vec = [0.1] * 384

        store.upsert("sections", "ica_10", vec, {
            "node_id": "ica_10", "doc_id": ICA_DOC_ID, "title": "ICA Section 10",
        })
        store.upsert("sections", "ipc_302", vec, {
            "node_id": "ipc_302", "doc_id": IPC_DOC_ID, "title": "IPC Section 302",
        })

        # Filtered search: only ICA
        hits = store.search("sections", vec, top_k=10, document_id=ICA_DOC_ID)
        node_ids = [h["node_id"] for h in hits]
        assert "ica_10" in node_ids
        assert "ipc_302" not in node_ids

        # Unfiltered search: both
        hits_all = store.search("sections", vec, top_k=10)
        node_ids_all = [h["node_id"] for h in hits_all]
        assert "ica_10" in node_ids_all
        assert "ipc_302" in node_ids_all
