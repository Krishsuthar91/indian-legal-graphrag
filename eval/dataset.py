"""Module 10, Part 1 — Gold-standard evaluation dataset.

Schema: query -> reference_answer -> citations.
Each item belongs to one legal domain (Indian Contract Act, Bharatiya Nyaya
Sanhita, Bharatiya Nagarik Suraksha Sanhita, Bharatiya Sakshya Adhiniyam, or
Supreme Court judgments). Items whose citations reference node ids present in
the on-disk corpus are ``grounded``; the rest are domain-expansion / generalisation
probes scored through citation-string matching.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DOMAINS = ("contract_act", "bns", "bnss", "bsa", "sc_judgments")

SCHEMA_VERSION = "1.0"

_CITATION_ALNUM = str.maketrans("", "", " ,.;:()[]{}'\"-–—_/\\")


def normalize_citation(text: str) -> str:
    """Lowercase, alphanumeric-only citation key used for matching."""
    return text.translate(_CITATION_ALNUM).lower()


@dataclass
class GoldCitation:
    """A gold citation attached to an evaluation item."""

    citation_text: str
    node_id: str | None = None
    label: str = ""
    numbering: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        self.node_id = self.node_id or None


@dataclass
class EvalItem:
    """One gold-standard question -> answer -> citations entry."""

    id: str
    domain: str
    query: str
    reference_answer: str
    citations: list[GoldCitation] = field(default_factory=list)
    language: str = "en"
    grounded: bool = False
    difficulty: str = "medium"
    expected_counter_authority_markers: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def gold_node_ids(self) -> set[str]:
        return {c.node_id for c in self.citations if c.node_id}

    @property
    def gold_citation_keys(self) -> set[str]:
        return {normalize_citation(c.citation_text) for c in self.citations}


@dataclass
class EvalDataset:
    """A validated collection of evaluation items."""

    name: str
    document_id: str
    items: list[EvalItem]
    meta: dict[str, Any] = field(default_factory=dict)

    def by_domain(self) -> dict[str, list[EvalItem]]:
        grouped: dict[str, list[EvalItem]] = {}
        for item in self.items:
            grouped.setdefault(item.domain, []).append(item)
        return grouped

    def grounded_items(self) -> list[EvalItem]:
        return [i for i in self.items if i.grounded]

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty when the dataset is valid)."""
        errors: list[str] = []
        seen: set[str] = set()
        for item in self.items:
            if item.id in seen:
                errors.append(f"duplicate item id: {item.id}")
            seen.add(item.id)
            if not item.id.strip():
                errors.append("item with empty id")
            if item.domain not in DOMAINS:
                errors.append(f"{item.id}: unknown domain {item.domain!r}")
            if not item.query.strip():
                errors.append(f"{item.id}: empty query")
            if not item.reference_answer.strip():
                errors.append(f"{item.id}: empty reference_answer")
            if not item.citations:
                errors.append(f"{item.id}: no gold citations")
            for citation in item.citations:
                if not citation.citation_text.strip():
                    errors.append(f"{item.id}: citation with empty citation_text")
                if item.grounded and not citation.node_id:
                    errors.append(
                        f"{item.id}: grounded citation without node_id "
                        f"({citation.citation_text})"
                    )
            if item.grounded and not item.gold_node_ids:
                errors.append(f"{item.id}: grounded item has no node-grounded citations")
            if item.language not in ("en", "hi", "bn", "ta", "te", "gu", "mr"):
                errors.append(f"{item.id}: unusual language {item.language!r}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "document_id": self.document_id,
            "meta": self.meta,
            "items": [
                {
                    **asdict(item),
                    "citations": [asdict(c) for c in item.citations],
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalDataset:
        items = [
            EvalItem(
                id=item.get("id", ""),
                domain=item.get("domain", ""),
                query=item.get("query", ""),
                reference_answer=item.get("reference_answer", ""),
                citations=[
                    GoldCitation(
                        citation_text=c.get("citation_text", ""),
                        node_id=c.get("node_id"),
                        label=c.get("label", ""),
                        numbering=c.get("numbering", ""),
                        title=c.get("title", ""),
                    )
                    for c in item.get("citations", [])
                ],
                language=item.get("language", "en"),
                grounded=item.get("grounded", False),
                difficulty=item.get("difficulty", "medium"),
                expected_counter_authority_markers=item.get(
                    "expected_counter_authority_markers", []
                ),
                notes=item.get("notes", ""),
            )
            for item in data.get("items", [])
        ]
        return cls(
            name=data.get("name", "unnamed"),
            document_id=data.get("document_id", ""),
            items=items,
            meta=data.get("meta", {}),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> EvalDataset:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


def load_gold_dataset(path: str | Path) -> EvalDataset:
    """Load and validate a gold dataset, raising ValueError on validation failure."""
    dataset = EvalDataset.load(path)
    errors = dataset.validate()
    if errors:
        raise ValueError(f"invalid gold dataset {Path(path).name}:\n" + "\n".join(errors))
    return dataset


def load_all_gold(gold_dir: str | Path) -> dict[str, EvalDataset]:
    """Load every ``*_gold.json`` file in a directory into a name->dataset map."""
    datasets: dict[str, EvalDataset] = {}
    for path in sorted(Path(gold_dir).glob("*_gold.json")):
        if path.name == "manifest.json":
            continue
        datasets[path.name] = load_gold_dataset(path)
    return datasets


def write_manifest(
    gold_dir: str | Path,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate dataset statistics into a ``manifest.json``."""
    datasets = load_all_gold(gold_dir)
    total = sum(len(d.items) for d in datasets.values())
    by_domain: dict[str, int] = {}
    grounded = 0
    for d in datasets.values():
        for item in d.items:
            by_domain[item.domain] = by_domain.get(item.domain, 0) + 1
            if item.grounded:
                grounded += 1
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_name": "explaintool-eval",
        "files": sorted(datasets),
        "total_items": total,
        "grounded_items": grounded,
        "by_domain": by_domain,
        "document_id": next(iter(datasets.values())).document_id,
        "meta": extra_meta or {},
    }
    Path(gold_dir, "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
