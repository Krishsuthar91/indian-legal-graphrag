"""Main legal hierarchy parser — orchestrates parsing, tree building, and validation.

Reads data/processed/*.json, identifies legal structure, builds the
adjacency tree + nested set index, validates, and writes to data/hierarchy/.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config.logging_config import get_logger
from src.hierarchy.models import HierarchyNode, ParsedHierarchy
from src.hierarchy.patterns import LVL_BODY, match_line
from src.hierarchy.tree_builder import build_hierarchy
from src.hierarchy.validators import validate_hierarchy

log = get_logger("hierarchy")

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
HIERARCHY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "hierarchy"


def _collect_text_pages(pages: list[dict]) -> list[tuple[str, int]]:
    """Flatten pages into (text, page_number) pairs."""
    result: list[tuple[str, int]] = []
    for page in pages:
        text = page.get("text", "")
        pnum = page.get("page_number", 1)
        if text.strip():
            result.append((text, pnum))
    return result


def _split_into_blocks(text_pages: list[tuple[str, int]]) -> list[dict]:
    """Split page text into logical blocks (paragraphs / lines).

    Returns list of dicts with keys: text, page_number, line_number.
    """
    blocks: list[dict] = []
    for text, page_num in text_pages:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped:
                blocks.append({
                    "text": stripped,
                    "page_number": page_num,
                    "line_number": i,
                })
    return blocks


def _merge_consecutive_body(blocks: list[dict], start_idx: int) -> tuple[str, int, int]:
    """Merge consecutive body lines into a single text block.

    Returns (merged_text, start_page, end_page).
    """
    texts: list[str] = []
    start_page = blocks[start_idx]["page_number"]
    end_page = start_page

    i = start_idx
    while i < len(blocks):
        block = blocks[i]
        match = match_line(block["text"])
        if match and match.level < LVL_BODY:
            break
        texts.append(block["text"])
        end_page = block["page_number"]
        i += 1

    return "\n".join(texts), start_page, end_page


def parse_document(processed_json: Path) -> ParsedHierarchy:
    """Parse a single processed document into a hierarchy.

    Steps:
    1. Load JSON from data/processed/
    2. Flatten pages into blocks
    3. Classify each block with numbering patterns
    4. Merge consecutive body text under the last structural node
    5. Build tree + nested set index
    6. Validate and collect warnings
    """
    data = json.loads(processed_json.read_text(encoding="utf-8"))
    document_id = data["document_id"]
    title = data.get("title", "")
    pages = data.get("pages", [])

    log.info("hierarchy.parse.start", document_id=document_id)

    text_pages = _collect_text_pages(pages)
    blocks = _split_into_blocks(text_pages)

    nodes: list[HierarchyNode] = []
    node_counter = 0

    i = 0
    while i < len(blocks):
        block = blocks[i]
        match = match_line(block["text"])

        if match and match.level < LVL_BODY:
            # Structural node found
            node_counter += 1
            node_id = f"n_{node_counter:04d}"
            node = HierarchyNode(
                node_id=node_id,
                level=match.level,
                node_type=match.node_type,
                title=match.title or match.numbering,
                text="",
                start_page=block["page_number"],
                end_page=block["page_number"],
                numbering=match.numbering,
            )
            nodes.append(node)
            i += 1

            # Collect body text that follows this structural node
            if i < len(blocks):
                next_match = match_line(blocks[i]["text"])
                if not next_match or next_match.level >= LVL_BODY:
                    body_text, sp, ep = _merge_consecutive_body(blocks, i)
                    if body_text.strip():
                        node.text = body_text
                        node.end_page = ep
                        # Advance past merged body lines
                        while i < len(blocks):
                            bm = match_line(blocks[i]["text"])
                            if bm and bm.level < LVL_BODY:
                                break
                            i += 1
        else:
            # Unmatched line — attach as body text to the last node
            if nodes:
                last = nodes[-1]
                extra = block["text"]
                if last.text:
                    last.text += "\n" + extra
                else:
                    last.text = extra
                last.end_page = block["page_number"]
            i += 1

    # Build tree
    hierarchy = build_hierarchy(document_id, title, nodes)

    # Validate
    validate_hierarchy(hierarchy)

    log.info(
        "hierarchy.parse.complete",
        document_id=document_id,
        nodes=len(hierarchy.nodes),
        warnings=len(hierarchy.warnings),
    )

    return hierarchy


def parse_and_save(processed_json: Path) -> ParsedHierarchy:
    """Parse a document and save the hierarchy to data/hierarchy/<document_id>.json."""
    hierarchy = parse_document(processed_json)

    HIERARCHY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = HIERARCHY_DIR / f"{hierarchy.document_id}.json"
    out_path.write_text(
        json.dumps(hierarchy.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("hierarchy.saved", path=str(out_path))
    return hierarchy


def parse_all() -> list[ParsedHierarchy]:
    """Parse all documents in data/processed/ and save hierarchies."""
    results: list[ParsedHierarchy] = []
    for json_file in sorted(PROCESSED_DIR.glob("*.json")):
        try:
            h = parse_and_save(json_file)
            results.append(h)
        except Exception as exc:
            log.error("hierarchy.parse.error", file=str(json_file), error=str(exc))
    return results
