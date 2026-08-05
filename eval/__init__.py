"""Module 10 — Research Evaluation & Publication Package."""

from eval.corpus import Corpus, build_corpus
from eval.dataset import (
    DOMAINS,
    EvalDataset,
    EvalItem,
    GoldCitation,
    load_all_gold,
    load_gold_dataset,
    normalize_citation,
    write_manifest,
)

__all__ = [
    "DOMAINS",
    "Corpus",
    "build_corpus",
    "EvalDataset",
    "EvalItem",
    "GoldCitation",
    "load_all_gold",
    "load_gold_dataset",
    "normalize_citation",
    "write_manifest",
]
