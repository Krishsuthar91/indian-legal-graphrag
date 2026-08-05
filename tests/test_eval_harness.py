"""Tests for the Module 10 corpus, systems, ablation, and harness."""

import pytest

from eval.ablation import ABLATION_VARIANTS, build_ablation_rows, run_ablation
from eval.corpus import build_corpus, resolve_hierarchy_file
from eval.dataset import EvalDataset
from eval.harness import (
    benchmark_explainability,
    benchmark_from_config,
    benchmark_ragas,
    benchmark_retrieval,
    coverage_stats,
    item_relevant_ids,
    run_benchmark,
)
from eval.systems import Bm25System, build_systems
from tests.conftest import EVAL_DOCUMENT_ID, EVAL_GOLD_DIR, EVAL_HIERARCHY_FILE


class TestCorpus:
    def test_build_corpus_counts(self, eval_corpus):
        assert eval_corpus.node_count == 11
        assert eval_corpus.edge_count == 10
        assert len(eval_corpus.all_nodes()) == 11

    def test_corpus_is_deterministic(self):
        first = build_corpus(document_id=EVAL_DOCUMENT_ID, hierarchy_file=str(EVAL_HIERARCHY_FILE))
        second = build_corpus(document_id=EVAL_DOCUMENT_ID, hierarchy_file=str(EVAL_HIERARCHY_FILE))
        try:
            first_result = first.engine.explain("performance of contracts", top_k=5)
            second_result = second.engine.explain("performance of contracts", top_k=5)
            assert [e.node_id for e in first_result.evidence] == [
                e.node_id for e in second_result.evidence
            ]
        finally:
            first.close()
            second.close()

    def test_resolve_hierarchy_file(self):
        path = resolve_hierarchy_file(EVAL_DOCUMENT_ID)
        assert path.exists()


class TestSystems:
    def test_build_systems_returns_five(self, eval_corpus):
        systems = build_systems(eval_corpus, with_answers=False)
        assert set(systems) == {"hhgr", "dense", "bm25", "graph", "naive_rag"}

    @pytest.mark.parametrize("name", ["hhgr", "dense", "bm25", "graph", "naive_rag"])
    def test_system_returns_ranked_hits(self, eval_corpus, name):
        systems = build_systems(eval_corpus, with_answers=False)
        result = systems[name].run("performance of contracts", top_k=5)
        assert result.system == name
        assert len(result.hits) <= 5
        assert all(hit.node_id for hit in result.hits)
        assert result.duration_ms >= 0.0

    def test_hhgr_explanation_present(self, eval_corpus):
        system = build_systems(eval_corpus, with_answers=True)["hhgr"]
        result = system.run("performance of contracts", top_k=5)
        assert result.explanation is not None
        assert result.explanation.evidence
        assert len(result.answer) > 0

    def test_naive_rag_produces_answer_without_explanation(self, eval_corpus):
        system = build_systems(eval_corpus, with_answers=True)["naive_rag"]
        result = system.run("performance of contracts", top_k=5)
        assert result.explanation is None
        assert len(result.answer) > 0

    def test_bm25_scores_positive(self, eval_corpus):
        bm25 = Bm25System(eval_corpus.graph)
        result = bm25.run("performance of contracts", top_k=5)
        assert all(hit.score >= 0.0 for hit in result.hits)


class TestItemRelevance:
    def test_grounded_item_uses_gold_node_ids(self, eval_corpus, eval_items):
        item = eval_items[0]
        assert item_relevant_ids(eval_corpus.graph, item) == item.gold_node_ids

    def test_ungrounded_item_matches_by_citation(self, eval_corpus):
        dataset = EvalDataset.load(EVAL_GOLD_DIR / "bns_gold.json")
        item = dataset.items[0]
        relevant = item_relevant_ids(eval_corpus.graph, item)
        assert isinstance(relevant, set)


class TestBenchmark:
    def test_benchmark_retrieval_rows(self, eval_corpus, eval_items):
        rows, per_query = benchmark_retrieval(
            eval_corpus, eval_items, top_k=5, systems=build_systems(eval_corpus, with_answers=False)
        )
        assert len(rows) == 5
        assert set(r["system"] for r in rows) == {"hhgr", "dense", "bm25", "graph", "naive_rag"}
        assert all("mrr" in r and "recall_at_k" in r for r in rows)
        assert len(per_query) == 5 * len(eval_items)

    def test_benchmark_explainability(self, eval_corpus, eval_items):
        rows = benchmark_explainability(eval_corpus, eval_items, top_k=5)
        assert len(rows) == len(eval_items)
        assert all("citation_accuracy" in r for r in rows)
        assert all("n_evidence" in r for r in rows)

    def test_benchmark_ragas(self, eval_corpus, eval_items):
        rows = benchmark_ragas(
            eval_corpus, eval_items, top_k=5, systems=build_systems(eval_corpus, with_answers=True)
        )
        assert len(rows) == 2 * len(eval_items)
        assert {r["system"] for r in rows} == {"hhgr", "naive_rag"}
        assert all("faithfulness" in r for r in rows)

    def test_run_benchmark_quick(self, eval_corpus, eval_dataset):
        output = run_benchmark(eval_dataset, eval_corpus, top_k=5, quick=True, seed=42)
        assert output.meta["quick"] is True
        assert output.meta["items_evaluated"] == 3
        assert len(output.retrieval) == 5
        assert output.ablation and set(output.ablation) == {v.name for v in ABLATION_VARIANTS}

    def test_benchmark_from_config(self):
        import json

        with open("data/eval/config/experiment.json", encoding="utf-8") as fh:
            config = json.load(fh)
        output = benchmark_from_config(config, out_dir=None, quick=True)
        assert output.meta["document_id"] == EVAL_DOCUMENT_ID
        assert output.meta["items_evaluated"] == 3

    def test_coverage_stats(self):
        datasets = {}
        for path in sorted(EVAL_GOLD_DIR.glob("*_gold.json")):
            datasets[path.name] = EvalDataset.load(path)
        stats = coverage_stats(datasets)
        assert stats["total_items"] == 34
        assert stats["by_domain"]["contract_act"]["grounded"] == 10


class TestAblation:
    def test_variant_names(self):
        assert [v.name for v in ABLATION_VARIANTS] == [
            "full",
            "no_graph",
            "no_hierarchy",
            "no_dense",
            "no_multilingual",
            "no_explainability",
        ]

    def test_run_ablation_returns_all_variants(self, eval_corpus, eval_items):
        results = run_ablation(eval_corpus, eval_items, top_k=5)
        assert set(results) == {v.name for v in ABLATION_VARIANTS}
        for row in results.values():
            assert "mrr" in row
            assert "label" in row

    def test_no_multilingual_preserves_explanation(self, eval_corpus, eval_items):
        variant = [v for v in ABLATION_VARIANTS if v.name == "no_multilingual"][0]
        system = variant.build(eval_corpus)
        result = system.run(eval_items[0].query, top_k=5)
        assert result.explanation is not None

    def test_no_explainability_has_no_explanation(self, eval_corpus, eval_items):
        variant = [v for v in ABLATION_VARIANTS if v.name == "no_explainability"][0]
        system = variant.build(eval_corpus)
        result = system.run(eval_items[0].query, top_k=5)
        assert result.explanation is None

    def test_build_ablation_rows(self):
        results = {"full": {"label": "Full HHGR", "mrr": 0.75, "items": 3}}
        rows = build_ablation_rows(results)
        assert rows[0]["ablation"] == "full"
        assert rows[0]["label"] == "Full HHGR"
