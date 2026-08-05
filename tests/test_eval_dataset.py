"""Tests for the Module 10 gold-standard dataset (eval/dataset.py)."""

from pathlib import Path

from eval.dataset import (
    EvalDataset,
    EvalItem,
    GoldCitation,
    load_all_gold,
    load_gold_dataset,
    normalize_citation,
    write_manifest,
)
from tests.conftest import EVAL_DOCUMENT_ID, EVAL_GOLD_DIR


class TestNormalizeCitation:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_citation("Section 4, Indian Contract Act (1872)") == (
            "section4indiancontractact1872"
        )

    def test_unicode_dash_removed(self):
        assert normalize_citation("Sec 4 – Act") == "sec4act"

    def test_empty_string(self):
        assert normalize_citation("") == ""


class TestEvalItem:
    def test_gold_node_ids_only_grounded(self):
        item = EvalItem(
            id="q1",
            domain="contract_act",
            query="q",
            reference_answer="a",
            citations=[
                GoldCitation(citation_text="Section 4", node_id="n_0001"),
                GoldCitation(citation_text="Section 5"),
            ],
            grounded=True,
        )
        assert item.gold_node_ids == {"n_0001"}
        assert item.gold_citation_keys == {
            normalize_citation("Section 4"),
            normalize_citation("Section 5"),
        }


class TestEvalDatasetValidation:
    def test_valid_dataset_passes(self):
        dataset = EvalDataset(
            name="test",
            document_id="doc",
            items=[
                EvalItem(
                    id="q1",
                    domain="contract_act",
                    query="performance",
                    reference_answer="answer",
                    citations=[GoldCitation(citation_text="Section 4")],
                )
            ],
        )
        assert dataset.validate() == []

    def test_duplicate_ids_detected(self):
        item = EvalItem(
            id="dup",
            domain="contract_act",
            query="q",
            reference_answer="a",
            citations=[GoldCitation(citation_text="Section 4")],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item, item])
        assert any("duplicate" in e for e in dataset.validate())

    def test_unknown_domain_detected(self):
        item = EvalItem(
            id="q1",
            domain="space_law",
            query="q",
            reference_answer="a",
            citations=[GoldCitation(citation_text="Section 4")],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item])
        assert any("unknown domain" in e for e in dataset.validate())

    def test_grounded_item_requires_node_id(self):
        item = EvalItem(
            id="q1",
            domain="contract_act",
            query="q",
            reference_answer="a",
            grounded=True,
            citations=[GoldCitation(citation_text="Section 4")],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item])
        errors = dataset.validate()
        assert any("grounded citation without node_id" in e for e in errors)

    def test_empty_query_detected(self):
        item = EvalItem(
            id="q1",
            domain="contract_act",
            query="   ",
            reference_answer="a",
            citations=[GoldCitation(citation_text="Section 4")],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item])
        assert any("empty query" in e for e in dataset.validate())

    def test_no_citations_detected(self):
        item = EvalItem(
            id="q1",
            domain="contract_act",
            query="q",
            reference_answer="a",
            citations=[],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item])
        assert any("no gold citations" in e for e in dataset.validate())


class TestRoundTrip:
    def test_to_dict_from_dict_roundtrip(self):
        item = EvalItem(
            id="q1",
            domain="contract_act",
            query="performance",
            reference_answer="answer",
            language="hi",
            grounded=True,
            difficulty="hard",
            citations=[
                GoldCitation(
                    citation_text="Section 4",
                    node_id="n_0001",
                    label="Section",
                    numbering="4",
                    title="Performance of contracts",
                )
            ],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item])
        restored = EvalDataset.from_dict(dataset.to_dict())
        assert restored.items[0].id == "q1"
        assert restored.items[0].citations[0].node_id == "n_0001"
        assert restored.items[0].language == "hi"
        assert restored.items[0].grounded is True

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        item = EvalItem(
            id="q1",
            domain="contract_act",
            query="q",
            reference_answer="a",
            citations=[GoldCitation(citation_text="Section 4")],
        )
        dataset = EvalDataset(name="test", document_id="doc", items=[item])
        path = tmp_path / "ds.json"
        dataset.save(path)
        loaded = EvalDataset.load(path)
        assert loaded.name == "test"
        assert loaded.items[0].query == "q"


class TestGoldDatasets:
    def test_contract_act_dataset_loads(self):
        dataset = load_gold_dataset(EVAL_GOLD_DIR / "contract_act_gold.json")
        assert dataset.document_id == EVAL_DOCUMENT_ID
        assert len(dataset.grounded_items()) == len(dataset.items) == 10

    def test_all_gold_files_validate(self):
        datasets = load_all_gold(EVAL_GOLD_DIR)
        assert "contract_act_gold.json" in datasets
        assert len(datasets) >= 5

    def test_manifest_totals(self, tmp_path: Path):
        manifest = write_manifest(EVAL_GOLD_DIR)
        assert manifest["total_items"] == 34
        assert manifest["grounded_items"] == 10

    def test_by_domain_coverage(self):
        datasets = load_all_gold(EVAL_GOLD_DIR)
        domains = {item.domain for d in datasets.values() for item in d.items}
        assert domains == {"contract_act", "bns", "bnss", "bsa", "sc_judgments"}
