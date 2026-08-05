"""End-to-end tests for the hierarchy parser."""

import json
from pathlib import Path

import pytest

from src.hierarchy.parser import parse_and_save, parse_document


@pytest.fixture()
def legal_pdf(tmp_path: Path) -> Path:
    """Create a multi-section legal PDF with proper hierarchy."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    p = tmp_path / "test_act.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    w, h = A4

    lines = [
        "THE INDIAN CONTRACT ACT, 1892",
        "PART I — PRELIMINARY",
        "CHAPTER I",
        "Preliminary",
        "Section 1.",
        "Short title and commencement.",
        "(1) This Act may be called the Indian Contract Act, 1892.",
        "(2) It shall come into force on the first day of July, 1892.",
        "Section 2.",
        "Definitions.",
        "In this Act, unless there is anything repugnant in the subject or context,",
        "(a) \"contract\" means an agreement enforceable by law;",
        "(b) \"promise\" means a proposal accepted.",
        "(i) where the proposal is made",
        "(ii) where the acceptance is communicated",
        "Explanation.—Nothing in this section shall apply to",
        "Illustration.—A says to B",
        "Proviso.—Provided that",
        "CHAPTER II",
        "Of Contracts",
        "Section 3.",
        "Communication of proposals.",
        "(1) The communication of proposals is complete",
        "PART II — PERFORMANCE",
        "CHAPTER III",
        "Of Performance",
        "Section 4.",
        "Performance of contracts.",
        "(a) where the contract provides",
        "(b) where no provision is made",
    ]

    y = h - 2 * cm
    for line in lines:
        if y < 2 * cm:
            c.showPage()
            y = h - 2 * cm
        c.setFont("Helvetica", 10)
        c.drawString(2.5 * cm, y, line)
        y -= 0.5 * cm

    c.save()
    return p


@pytest.fixture()
def sample_processed_json(tmp_path: Path, legal_pdf: Path) -> Path:
    """Ingest the sample PDF and return the processed JSON path."""
    from src.ingestion.pipeline import ingest_document

    doc = ingest_document(legal_pdf)
    return Path(f"data/processed/{doc.document_id}.json")


class TestParseDocument:
    def test_parse_returns_hierarchy(self, sample_processed_json: Path):
        h = parse_document(sample_processed_json)
        assert h.document_id
        assert h.root_id == "root"
        assert len(h.nodes) > 0

    def test_parse_finds_chapters(self, sample_processed_json: Path):
        h = parse_document(sample_processed_json)
        chapters = [n for n in h.nodes if n.node_type == "chapter"]
        assert len(chapters) >= 2

    def test_parse_finds_sections(self, sample_processed_json: Path):
        h = parse_document(sample_processed_json)
        sections = [n for n in h.nodes if n.node_type == "section"]
        assert len(sections) >= 3

    def test_parse_has_nested_set(self, sample_processed_json: Path):
        h = parse_document(sample_processed_json)
        assert len(h.nested_set) == len(h.nodes)
        for entry in h.nested_set:
            assert entry.left < entry.right

    def test_parse_parent_child(self, sample_processed_json: Path):
        h = parse_document(sample_processed_json)
        node_map = {n.node_id: n for n in h.nodes}
        for node in h.nodes:
            if node.parent_id and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                assert node.node_id in parent.children


class TestParseAndSave:
    def test_saves_json(self, sample_processed_json: Path):
        h = parse_and_save(sample_processed_json)
        out_path = Path(f"data/hierarchy/{h.document_id}.json")
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert "nodes" in data
        assert "nested_set" in data
        assert "warnings" in data

    def test_saved_json_has_correct_structure(self, sample_processed_json: Path):
        h = parse_and_save(sample_processed_json)
        out_path = Path(f"data/hierarchy/{h.document_id}.json")
        data = json.loads(out_path.read_text())
        for node in data["nodes"]:
            assert "node_id" in node
            assert "level" in node
            assert "node_type" in node
            assert "start_page" in node
            assert "end_page" in node
        for entry in data["nested_set"]:
            assert "left" in entry
            assert "right" in entry
            assert "depth" in entry
