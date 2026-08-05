"""Graph importer — converts hierarchy JSON into Neo4j / in-memory graph nodes and edges."""

from __future__ import annotations

import json
from pathlib import Path

from src.config.logging_config import get_logger
from src.knowledge_graph.citation_extractor import extract_citations
from src.knowledge_graph.schema import (
    HIERARCHY_TYPE_MAP,
    NodeLabel,
    RelType,
    get_cypher_setup,
)

log = get_logger("importer")


def _get_label(hierarchy_type: str) -> str:
    return HIERARCHY_TYPE_MAP.get(hierarchy_type, NodeLabel.SECTION).value


def import_hierarchy_json(graph, hierarchy_path: Path) -> dict[str, int]:
    """Import a single hierarchy JSON file into the graph.

    Returns counts of nodes and edges created.
    """
    data = json.loads(hierarchy_path.read_text(encoding="utf-8"))
    doc_id = data["document_id"]
    nodes = data.get("nodes", [])

    nodes_created = 0
    edges_created = 0

    # 1. Create Document node
    root_node = next((n for n in nodes if n["node_id"] == "root"), None)
    doc_title = root_node["title"] if root_node else doc_id
    graph.create_node(
        NodeLabel.DOCUMENT.value, doc_id,
        {"document_id": doc_id, "title": doc_title, "language": data.get("language", "unknown")},
    )
    nodes_created += 1

    # 2. Create structural nodes and PART_OF edges
    node_id_map: dict[str, str] = {}  # hierarchy node_id -> graph node_id
    node_id_map["root"] = doc_id

    for h_node in nodes:
        if h_node["node_id"] == "root":
            continue

        h_type = h_node.get("node_type", "section")
        label = _get_label(h_type)
        graph_node_id = h_node["node_id"]

        props = {
            "node_id": graph_node_id,
            "hierarchy_level": h_node.get("level", 0),
            "title": h_node.get("title", ""),
            "text": h_node.get("text", ""),
            "numbering": h_node.get("numbering", ""),
            "start_page": h_node.get("start_page", 1),
            "end_page": h_node.get("end_page", 1),
        }

        graph.create_node(label, graph_node_id, props)
        nodes_created += 1
        node_id_map[h_node["node_id"]] = graph_node_id

        # PART_OF edge to parent
        parent_id = h_node.get("parent_id")
        if parent_id and parent_id in node_id_map:
            graph.create_edge(graph_node_id, node_id_map[parent_id], RelType.PART_OF.value)
            edges_created += 1

    # 3. Extract citations from text and create citation/reference edges
    for h_node in nodes:
        text = h_node.get("text", "")
        if not text:
            continue

        citations = extract_citations(text)
        source_id = node_id_map.get(h_node["node_id"])
        if not source_id:
            continue

        for cite in citations:
            if cite.citation_type == "case":
                # Create Case node and CITES edge
                case_id = f"case_{cite.case_name[:50]}"
                graph.merge_node(
                    NodeLabel.CASE.value, "citation", cite.case_name,
                    {"citation": cite.case_name, "court": cite.court, "year": cite.year},
                )
                if graph.create_edge(source_id, case_id, RelType.CITES.value):
                    edges_created += 1

                # Create Court node if court is identified
                if cite.court:
                    court_id = f"court_{cite.court}"
                    graph.merge_node(NodeLabel.COURT.value, "name", cite.court, {"name": cite.court})
                    graph.create_edge(case_id, court_id, RelType.PART_OF.value)

            else:
                # Section / Rule / Article — create LegalConcept node
                concept_name = cite.raw_text
                concept_id = f"concept_{concept_name[:50]}"
                graph.merge_node(
                    NodeLabel.LEGAL_CONCEPT.value, "name", concept_name,
                    {"name": concept_name, "citation_type": cite.citation_type, "ref_number": cite.ref_number},
                )
                if graph.create_edge(source_id, concept_id, RelType.REFERENCES.value):
                    edges_created += 1

    log.info(
        "import.complete",
        file=str(hierarchy_path),
        nodes=nodes_created,
        edges=edges_created,
    )
    return {"nodes_created": nodes_created, "edges_created": edges_created}


def import_all(graph, hierarchy_dir: Path | None = None) -> dict[str, int]:
    """Import all hierarchy JSON files from the given directory.

    Returns aggregate counts.
    """
    if hierarchy_dir is None:
        hierarchy_dir = Path(__file__).resolve().parent.parent.parent / "data" / "hierarchy"

    total_nodes = 0
    total_edges = 0
    files_imported = 0

    for json_file in sorted(hierarchy_dir.glob("*.json")):
        try:
            counts = import_hierarchy_json(graph, json_file)
            total_nodes += counts["nodes_created"]
            total_edges += counts["edges_created"]
            files_imported += 1
        except Exception as exc:
            log.error("import.error", file=str(json_file), error=str(exc))

    log.info("import.all_complete", files=files_imported, nodes=total_nodes, edges=total_edges)
    return {
        "files_imported": files_imported,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
    }


def setup_schema(graph) -> None:
    """Apply indexes and constraints if using Neo4j."""
    if hasattr(graph, "run_setup"):
        graph.run_setup(get_cypher_setup())
        log.info("schema.setup_complete")
