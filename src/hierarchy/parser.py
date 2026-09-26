"""Main legal hierarchy parser — orchestrates parsing, tree building, and validation.

Reads data/processed/*.json, identifies legal structure, builds the
adjacency tree + nested set index, validates, and writes to data/hierarchy/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.config.logging_config import get_logger
from src.hierarchy.models import HierarchyNode, ParsedHierarchy
from src.hierarchy.patterns import LVL_BODY, match_line
from src.hierarchy.tree_builder import build_hierarchy
from src.hierarchy.validators import validate_hierarchy

log = get_logger("hierarchy")

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
HIERARCHY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "hierarchy"

# ---------------------------------------------------------------------------
# Front-matter (table of contents) detection
# ---------------------------------------------------------------------------

# Headings that introduce a document's table of contents.  When a document
# opens with one of these (e.g. "ARRANGEMENT OF SECTIONS", "CONTENTS"), the
# listing it introduces mirrors the real body headings and would otherwise
# be parsed a second time, creating duplicate hierarchy trees.
_TOC_MARKERS = [
    r"ARRANGEMENT\s+OF\s+SECTIONS",
    r"TABLE\s+OF\s+CONTENTS",
    r"CONTENTS",
    r"INDEX",
]
_TOC_MARKER_RE = re.compile(
    rf"^\s*(\d+\s*[\.\-:]?\s*)?(?:{'|'.join(_TOC_MARKERS)})\s*$", re.IGNORECASE
)

# Lines that mark where the real body begins after the front matter — an act
# citation such as "ACT NO. 45 OF 1860" or "[9 OF 1872]".
_BODY_START_RE = re.compile(
    r"(?:"
    r"(?:ACT\s+NO\.\s*\d{1,4}\s+OF\s+\d{3,4})"
    r"|\[\s*\d{1,4}\s+OF\s+\d{3,4}\s*\]"
    r")",
    re.IGNORECASE,
)


def _find_body_start(blocks: list[dict]) -> int | None:
    """Return the block index where the real body begins.

    When a document opens with front matter (a table of contents), all blocks
    up to the first act citation belong to that listing and must be skipped so
    their headings do not duplicate the body hierarchy.  Returns ``None`` when
    no front matter is detected (parse everything as before).
    """
    marker_idx = None
    for i, block in enumerate(blocks[:300]):
        if _TOC_MARKER_RE.match(block["text"]):
            marker_idx = i
            break
    if marker_idx is None:
        return None

    marker_page = blocks[marker_idx]["page_number"]
    for j in range(marker_idx + 1, min(marker_idx + 600, len(blocks))):
        block = blocks[j]
        if _BODY_START_RE.search(block["text"]) and block["page_number"] >= marker_page:
            return j
    return None


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
                blocks.append(
                    {
                        "text": stripped,
                        "page_number": page_num,
                        "line_number": i,
                    }
                )
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


# ---------------------------------------------------------------------------
# Fragment suppression
# ---------------------------------------------------------------------------

# Node types that are headed fragments of a statutory provision rather than
# standalone provisions.  Explanations, illustrations and provisos annotate the
# section they appear in; when stored as independent nodes they surface as
# malformed "evidence fragments" (e.g. an isolated "Illustration" node carrying
# a truncated tail).  They belong inside the section's body text instead.
_FRAGMENT_NODE_TYPES = frozenset({"explanation", "illustration", "proviso"})

# A section whose heading begins with a lowercase letter is a wrapped body
# tail, never a real statutory heading (e.g. "294A. of the Indian Penal Code
# not affected : …", "76. to 123 — Repealed").  Such lines created a false
# section boundary where the document merely wrapped a sentence across lines.
_LOWERCASE_START_RE = re.compile(r"^[a-z]")

# Footnote-editing notes (e.g. "The words \"Thirdly,\" ... omitted by Act 17 of
# 1949") parsed their opening phrase as a section heading.  Such headings open
# with the literals "The words" followed by a quotation mark.
_FOOTNOTE_SECTION_RE = re.compile(r"^The words [\u201c\"]")


def suppress_fragment_nodes(nodes: list[HierarchyNode]) -> list[HierarchyNode]:
    """Merge malformed fragment nodes into the nearest preceding sibling.

    Suppresses residual parser fragments so they never become independent
    legal provisions:

    * annotation headings (Explanation / Illustration / Proviso) — their
      content belongs inside the section they annotate, so it is folded back
      into the preceding node's text;
    * false section nodes whose heading is a wrapped body tail (lowercase
      start) — the text is kept, the bogus boundary removed.

    Valid provisions are left untouched.  Returns the filtered node list.
    """
    result: list[HierarchyNode] = []
    for node in nodes:
        title = node.title or ""
        is_fragment = node.node_type in _FRAGMENT_NODE_TYPES or (
            node.node_type == "section"
            and (bool(_LOWERCASE_START_RE.match(title)) or bool(_FOOTNOTE_SECTION_RE.match(title)))
        )
        if not is_fragment:
            result.append(node)
            continue

        merged = "\n".join(part for part in (title, node.text) if part)
        if merged and result:
            prev = result[-1]
            prev.text = f"{prev.text}\n{merged}" if prev.text else merged
    return result


# ---------------------------------------------------------------------------
# Embedded-section splitter
# ---------------------------------------------------------------------------

# Matches a bare section-number heading embedded in a line, e.g.
#   "10. What agreements are contracts"
# Number: 1-3 digits with optional letter suffix.  Title starts with a
# capital letter or opening quote.
_EMBEDDED_SECTION_RE = re.compile(r"(\d{1,3}[A-Za-z]*)\.\s+([A-Z\u201C\u2018])")

# Matches an embedded section heading whose statutory body begins on the
# same line, separated by an em dash / en dash (or hyphen pair), e.g.
#   "Of Theft 378. Theft.—Whoever, intending to take dishonestly…"
#   "himself to be likely to cause. 302. Punishment for murder.—Whoever…"
# Number: 1-3 digits with optional letter suffix.  Title starts with a
# capital letter or opening quote and may not contain a dash, so the
# heading always stops at the dash that introduces the body text.
_EMBEDDED_EMDASH_SECTION_RE = re.compile(
    r"\b(\d{1,3}[A-Za-z]*)\.\s+([A-Z\u201C\u2018][^0-9\u2014\u2013]*?)\s*(?:\u2014|\u2013|--)"
)

# Matches a heading with a trailing section number, e.g.
#   "Punishment for murder 302."
# Title starts with a capital letter or opening quote and contains no
# interior period, so prose sentences are not mistaken for headings.
_EMBEDDED_TRAILING_SECTION_RE = re.compile(
    r"^([A-Z\u201C\u2018][^0-9.]*?)\s+(\d{1,3}[A-Za-z]*)\.\s*$"
)


def _split_embedded_sections(text: str) -> list[str]:
    """Split a line that contains an embedded section heading.

    Handles the case where text cleaning merged a section heading onto the
    same line as a parent chapter / part heading, a chapter-descriptive
    prefix (e.g. "Of Theft 378. Theft."), preceding body text, or a trailing
    section number (e.g. "Punishment for murder 302.").  Returns ``[text]``
    when no split is needed.

    Examples::

        "Chapter II Of contracts… 10. What agreements are contracts"
        → ["Chapter II Of contracts…", "10. What agreements are contracts"]

        "Of Theft 378. Theft.—Whoever, intending to take dishonestly…"
        → ["Of Theft", "378. Theft", "Whoever, intending to take dishonestly…"]

        "Punishment for murder 302."
        → ["302. Punishment for murder"]
    """
    # 1) Parent chapter / part heading with an embedded section heading:
    #    split off the heading; behaviour preserved unchanged.
    if re.match(r"^\s*(?:CHAPTER|Chapter|PART|Part)\s+", text, re.I):
        for m in _EMBEDDED_SECTION_RE.finditer(text):
            before = text[: m.start()].strip()
            after = text[m.start() :].strip()
            if before and after and len(before) > 5:
                return [before, after]
        return [text]

    # 2) Embedded section heading with a dash-introduced body on the same
    #    line.  Requires preceding text on the line, so standalone headings
    #    that are already matched by the line-start numbering patterns are
    #    left untouched.
    m = _EMBEDDED_EMDASH_SECTION_RE.search(text)
    if m:
        prefix = text[: m.start()].strip()
        if prefix:
            title = m.group(2).strip().rstrip(".")
            parts = [prefix, f"{m.group(1)}. {title}"]
            body = text[m.end() :].strip()
            if body:
                parts.append(body)
            return parts
        return [text]

    # 3) Heading with a trailing section number at the end of the line:
    #    canonicalise into "<number>. <title>" so the existing numbering
    #    patterns classify it as a section.
    m = _EMBEDDED_TRAILING_SECTION_RE.match(text)
    if m:
        return [f"{m.group(2)}. {m.group(1).strip()}"]

    return [text]


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

    # Skip front matter (table of contents) so its mirrored headings do not
    # create duplicate hierarchy trees alongside the real body headings.
    body_start = _find_body_start(blocks)
    if body_start is not None:
        log.info(
            "hierarchy.parse.front_matter",
            document_id=document_id,
            skipped_blocks=body_start,
        )
        blocks = blocks[body_start:]

    # Split chapter / part lines that contain embedded section headings
    expanded: list[dict] = []
    for block in blocks:
        for part in _split_embedded_sections(block["text"]):
            expanded.append({**block, "text": part})
    blocks = expanded

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

    # Suppress residual parser fragments (isolated illustration /
    # explanation / proviso headings and false section boundaries) before
    # building the tree, so they never become independent provisions.
    nodes = suppress_fragment_nodes(nodes)

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
