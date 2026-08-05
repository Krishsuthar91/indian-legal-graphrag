"""Neo4j driver abstraction — real driver + in-memory graph for testing."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-Memory Graph (used for tests and when Neo4j is unavailable)
# ---------------------------------------------------------------------------

class InMemoryGraph:
    """A lightweight in-memory graph store that mirrors Neo4j's API surface."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}       # node_id -> properties
        self._node_labels: dict[str, str] = {}             # node_id -> label
        self._edges: list[dict[str, Any]] = []             # list of edge dicts
        self._adj_out: dict[str, list[int]] = defaultdict(list)  # node_id -> edge indices
        self._adj_in: dict[str, list[int]] = defaultdict(list)

    # -- Node operations ---------------------------------------------------

    def create_node(self, label: str, node_id: str, props: dict[str, Any] | None = None) -> str:
        merged = {"node_id": node_id, "label": label}
        if props:
            merged.update(props)
        self._nodes[node_id] = merged
        self._node_labels[node_id] = label
        return node_id

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    def get_nodes_by_label(self, label: str) -> list[dict[str, Any]]:
        return [n for nid, n in self._nodes.items() if self._node_labels.get(nid) == label]

    def all_nodes(self) -> list[dict[str, Any]]:
        return list(self._nodes.values())

    def find_nodes(self, label: str, property_key: str, property_value: Any) -> list[dict[str, Any]]:
        return [
            n for nid, n in self._nodes.items()
            if self._node_labels.get(nid) == label and n.get(property_key) == property_value
        ]

    def merge_node(self, label: str, match_key: str, match_value: Any, props: dict[str, Any] | None = None) -> str:
        existing = self.find_nodes(label, match_key, match_value)
        if existing:
            nid = existing[0]["node_id"]
            if props:
                self._nodes[nid].update(props)
            return nid
        import uuid
        nid = uuid.uuid4().hex[:12]
        all_props = {match_key: match_value}
        if props:
            all_props.update(props)
        self.create_node(label, nid, all_props)
        return nid

    def delete_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            return
        for idx in self._adj_out.get(node_id, []):
            edge = self._edges[idx]
            in_list = self._adj_in.get(edge["to_node"], [])
            if idx in in_list:
                in_list.remove(idx)
        for idx in self._adj_in.get(node_id, []):
            edge = self._edges[idx]
            out_list = self._adj_out.get(edge["from_node"], [])
            if idx in out_list:
                out_list.remove(idx)
        self._adj_out.pop(node_id, None)
        self._adj_in.pop(node_id, None)
        del self._nodes[node_id]
        self._node_labels.pop(node_id, None)

    # -- Edge operations ---------------------------------------------------

    def create_edge(self, from_node: str, to_node: str, rel_type: str, props: dict[str, Any] | None = None) -> int:
        edge_idx = len(self._edges)
        edge: dict[str, Any] = {"from_node": from_node, "to_node": to_node, "rel_type": rel_type}
        if props:
            edge.update(props)
        self._edges.append(edge)
        self._adj_out[from_node].append(edge_idx)
        self._adj_in[to_node].append(edge_idx)
        return edge_idx

    def get_edges(self, node_id: str, rel_type: str | None = None, direction: str = "both") -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if direction in ("out", "both"):
            for idx in self._adj_out.get(node_id, []):
                edge = self._edges[idx]
                if rel_type is None or edge["rel_type"] == rel_type:
                    result.append(edge)
        if direction in ("in", "both"):
            for idx in self._adj_in.get(node_id, []):
                edge = self._edges[idx]
                if rel_type is None or edge["rel_type"] == rel_type:
                    result.append(edge)
        return result

    def find_edge(self, from_node: str, to_node: str, rel_type: str) -> dict[str, Any] | None:
        for idx in self._adj_out.get(from_node, []):
            edge = self._edges[idx]
            if edge["to_node"] == to_node and edge["rel_type"] == rel_type:
                return edge
        return None

    def delete_edge(self, from_node: str, to_node: str, rel_type: str) -> bool:
        for idx in list(self._adj_out.get(from_node, [])):
            edge = self._edges[idx]
            if edge["to_node"] == to_node and edge["rel_type"] == rel_type:
                in_list = self._adj_in.get(to_node, [])
                if idx in in_list:
                    in_list.remove(idx)
                self._edges[idx] = {"_deleted": True}
                self._adj_out[from_node].remove(idx)
                return True
        return False

    def merge_edge(self, from_node: str, to_node: str, rel_type: str, props: dict[str, Any] | None = None) -> bool:
        existing = self.find_edge(from_node, to_node, rel_type)
        if existing:
            if props:
                existing.update(props)
            return False
        self.create_edge(from_node, to_node, rel_type, props)
        return True

    # -- Stats -------------------------------------------------------------

    def node_count(self, label: str | None = None) -> int:
        if label:
            return len(self.get_nodes_by_label(label))
        return len(self._nodes)

    def edge_count(self, rel_type: str | None = None) -> int:
        if rel_type:
            return sum(1 for e in self._edges if not e.get("_deleted") and e["rel_type"] == rel_type)
        return sum(1 for e in self._edges if not e.get("_deleted"))

    def clear(self) -> None:
        self._nodes.clear()
        self._node_labels.clear()
        self._edges.clear()
        self._adj_out.clear()
        self._adj_in.clear()


# ---------------------------------------------------------------------------
# Neo4j Driver (wraps the real neo4j package)
# ---------------------------------------------------------------------------

class Neo4jDriver:
    """Thin wrapper around the official neo4j driver."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        log.info("neo4j.connected", uri=uri)

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

    def execute_write(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            def _tx(tx):
                result = tx.run(cypher, params or {})
                return [dict(record) for record in result]
            return session.execute_write(_tx)

    def create_node(self, label: str, node_id: str, props: dict[str, Any] | None = None) -> str:
        query = f"MERGE (n:{label} {{node_id: $node_id}}) SET n += $props RETURN n.node_id AS id"
        p = {"node_id": node_id, "props": props or {}}
        self.run(query, p)
        return node_id

    def create_edge(self, from_node: str, to_node: str, rel_type: str, props: dict[str, Any] | None = None) -> bool:
        query = (
            f"MATCH (a {{node_id: $from_id}}), (b {{node_id: $to_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r += $props RETURN type(r) AS t"
        )
        result = self.run(query, {"from_id": from_node, "to_id": to_node, "props": props or {}})
        return len(result) > 0

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        result = self.run("MATCH (n {node_id: $id}) RETURN properties(n) AS props", {"id": node_id})
        return result[0]["props"] if result else None

    def find_nodes(self, label: str, key: str, value: Any) -> list[dict[str, Any]]:
        query = f"MATCH (n:{label} {{{key}: $val}}) RETURN properties(n) AS props"
        return [r["props"] for r in self.run(query, {"val": value})]

    def all_nodes(self) -> list[dict[str, Any]]:
        result = self.run("MATCH (n) RETURN properties(n) AS props")
        return [r["props"] for r in result]

    def get_neighbors(self, node_id: str, rel_type: str | None = None, direction: str = "both") -> list[dict[str, Any]]:
        if direction == "out":
            rel_clause = f"-[r:{rel_type}]->" if rel_type else "-[r]->"
            query = f"MATCH (n {{node_id: $id}}){rel_clause}(m) RETURN properties(m) AS props, type(r) AS rel"
        elif direction == "in":
            rel_clause = f"<-[r:{rel_type}]-" if rel_type else "<-[r]-"
            query = f"MATCH (n {{node_id: $id}}){rel_clause}(m) RETURN properties(m) AS props, type(r) AS rel"
        else:
            rel_clause = f"-[r:{rel_type}]-" if rel_type else "-[r]-"
            query = f"MATCH (n {{node_id: $id}}){rel_clause}(m) RETURN properties(m) AS props, type(r) AS rel"
        return self.run(query, {"id": node_id})

    def delete_node(self, node_id: str) -> None:
        self.run("MATCH (n {node_id: $id}) DETACH DELETE n", {"id": node_id})

    def delete_edge(self, from_node: str, to_node: str, rel_type: str) -> bool:
        query = (
            f"MATCH (a {{node_id: $fid}})-[r:{rel_type}]->(b {{node_id: $tid}}) DELETE r RETURN 1"
        )
        result = self.run(query, {"fid": from_node, "tid": to_node})
        return len(result) > 0

    def node_count(self, label: str | None = None) -> int:
        if label:
            result = self.run(f"MATCH (n:{label}) RETURN count(n) AS c")
        else:
            result = self.run("MATCH (n) RETURN count(n) AS c")
        return result[0]["c"] if result else 0

    def edge_count(self, rel_type: str | None = None) -> int:
        if rel_type:
            result = self.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS c")
        else:
            result = self.run("MATCH ()-[r]->() RETURN count(r) AS c")
        return result[0]["c"] if result else 0

    def run_setup(self, statements: list[str]) -> None:
        for stmt in statements:
            self.run(stmt)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_graph(uri: str | None = None, user: str | None = None, password: str | None = None):
    """Return a graph store.

    If Neo4j credentials are provided and reachable, return Neo4jDriver.
    Otherwise, return InMemoryGraph.
    """
    if uri and user and password:
        try:
            driver = Neo4jDriver(uri, user, password)
            driver.run("RETURN 1")
            return driver
        except Exception as exc:
            log.warning("neo4j.unavailable, using in-memory graph: %s", exc)
    return InMemoryGraph()
