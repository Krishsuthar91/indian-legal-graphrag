# 05 — Database Design

The system deliberately separates **structured legal relationships** (a knowledge graph)
from **semantic similarity** (a vector store), and persists derived artefacts as JSON on
disk. This document specifies all three stores.

Primary sources: `src/knowledge_graph/` (`schema.py`, `importer.py`, `neo4j_driver.py`,
`traversal.py`, `citation_extractor.py`), `src/embeddings/` (`store.py`, `models.py`),
`src/hierarchy/models.py`, `src/llm/provenance.py`.

---

## 5.1 Storage overview

| Store | Technology | Role | Production | Dev/test |
|-------|-----------|------|-----------|----------|
| Knowledge graph | Neo4j 5 | Legal hierarchy + cross-references | yes | `InMemoryGraph` |
| Vector store | Qdrant | Dense semantic search over 4 granularities | yes | in-memory / deterministic |
| Blob store | Filesystem JSON | hierarchy, processed docs, provenance, embeddings | yes | yes |
| Cache / queue | Redis 6 | reserved / optional | yes | optional |

A design rule runs through everything: **the same logical node id is used by the graph, the
vector store, and provenance**, so a retrieved vector always resolves back to a graph node
and a citation. The canonical id is the ingestion-time content-addressed id produced by
`src/ingestion/identity.py`.

---

## 5.2 Knowledge-graph model

### 5.2.1 Node labels

Defined in `src/knowledge_graph/schema.py`:

| Label | Meaning | Key properties |
|-------|---------|----------------|
| `Document` | A whole Act / judgment | `document_id`, `title`, `act_name`, `year`, `source_path` |
| `Chapter` | A chapter/part within a document | `node_id`, `number`, `title`, `document_id` |
| `Section` | A section/article | `node_id`, `section_number`, `title`, `text`, `document_id`, `in_force` |
| `Clause` | A sub-clause / illustration / proviso | `node_id`, `clause_number`, `text`, `document_id` |
| `Act` | Canonical Act entity used for resolution | `act_key`, `canonical_document_id`, `title` |

Each hierarchy node carries a monotonic integer id from the hierarchy parser
(`src/hierarchy/models.py`) that is stable for a given parsed document.

### 5.2.2 Relationship types

| Type | Direction | Meaning |
|------|-----------|---------|
| `PART_OF` | child → parent | Structural containment (Clause→Section→Chapter→Document) |
| `CITES` | Section → Section | Explicit cross-reference extracted from text |
| `REFERENCES` | node → node | Weaker/implicit reference (e.g. "as defined in …") |
| `DEFINES` (where present) | Section → term | Definitional relation used for expansion |

`PART_OF` is the backbone of hierarchy-aware retrieval: the retriever walks these edges up to
ancestors and down to siblings/descendants (`src/knowledge_graph/traversal.py`,
`src/retrieval/context.py:89-149`).

### 5.2.3 Graph schema (Cypher shape)

```cypher
(:Document {document_id, title, act_name, year, source_path})
    ←[:PART_OF]-(:Chapter {node_id, number, title})
                     ←[:PART_OF]-(:Section {node_id, section_number, title, text, in_force})
                                        ←[:PART_OF]-(:Clause {node_id, clause_number, text})

(:Section)-[:CITES {source:"regex", confidence:float}]->(:Section)
(:Document)-[:IS_ACT]->(:Act {act_key, canonical_document_id})
```

Indexes/constraints (created in `src/knowledge_graph/schema.py`): uniqueness on
`Section.node_id`, `Clause.node_id`, `Document.document_id`, and `Act.act_key`;
full-text index on `Section.text`.

### 5.2.4 In-memory graph

`src/knowledge_graph/importer.py` maintains an `InMemoryGraph` (adjacency maps keyed by node
id) used by tests, the offline `eval/` harness, and any environment without a running Neo4j.
`neo4j_driver.py` provides the equivalent Neo4j-backed implementation behind the same
interface, selected by `settings` (`GRAPH_BACKEND` / component availability).

### 5.2.5 Canonical corpus

`src/knowledge_graph/canonical.py` groups the many duplicate hierarchy files by a normalised
Act title and nominates one **canonical** document per Act, eliminating ambiguity in imports
and evaluation. Verified mappings include:

| Normalised query term | Canonical document id |
|-----------------------|-----------------------|
| `indian contract act` | `0d1934142f67c5f5` |
| `indian penal code` | `cf20a14c52127fd5` |

### 5.2.6 Citation extraction

`src/knowledge_graph/citation_extractor.py` scans section text with legal-reference patterns
(`Section 2(h)`, `s. 378`, `Article 21`, `u/s 302 IPC`, …) to populate `CITES` edges, which
feed both the graph signal during retrieval and the citation signal in explanations.

---

## 5.3 Vector store model (Qdrant)

### 5.3.1 Collections

Configured in `src/embeddings/models.py:92-101` and created in `src/embeddings/store.py`:

| Collection | Indexed unit | Typical use |
|-----------|--------------|-------------|
| `documents` | whole-document summary/opening | document-level recall |
| `chapters` | chapter text | chapter-level recall |
| `sections` | section text | primary retrieval granularity |
| `clauses` | clause/illustration text | fine-grained retrieval |

All collections use **cosine** distance. Vector dimension is determined by the active
embedding model (`src/embeddings/models.py:37-84`).

### 5.3.2 Payload schema

Each point payload carries enough metadata to reconstruct provenance without a graph lookup:

```json
{
  "document_id": "0940d367554383c5",
  "node_id": 1234,
  "level": "section",
  "section_number": "378",
  "title": "Theft",
  "text": "Whoever, intending to take dishonestly …",
  "act_name": "Indian Penal Code",
  "hierarchy_path": ["Indian Penal Code", "Chapter XVII", "378"],
  "in_force": true
}
```

### 5.3.3 Embedding providers / dimensions

| Provider / model | Dim | Notes |
|------------------|-----|-------|
| `BAAI/bge-m3` (default) | 1024 | multilingual, best quality |
| `BAAI/bge-large-en-v1.5` | 1024 | English-optimised |
| `intfloat/e5-large-v2` | 1024 | strong English baseline |
| `sentence-transformers/LaBSE` | 768 | multilingual |
| `google/muril-base-cased` | 768 | Indic languages |
| `ai4bharat/indic-bert` | 768 | Indic languages |
| `deterministic` | 384 | hash-based; **tests/eval only** unless fallback explicitly enabled |

Switching provider requires re-indexing because dimensions differ
(`src/embeddings/indexer.py`, `src/embeddings/benchmark.py`).

### 5.3.4 Retrieval interface

`src/embeddings/retriever.py:23-27` fuses **dense** (Qdrant) + **graph** (4-signal HHGR) +
**hierarchy** scores. `src/embeddings/store.py` wraps the Qdrant client; `indexer.py` upserts
points during ingestion; `service.py` is the high-level facade used by the API.

---

## 5.4 Filesystem blob store

### 5.4.1 Hierarchy (`data/hierarchy/<document_id>.json`)

Written by `src/hierarchy/parser.py`; nested tree of `Document/Chapter/Section/Clause` with
node ids, numbering, titles, text, and cross-reference placeholders. **295 files** present.

Example shape:
```json
{
  "document_id": "0940d367554383c5",
  "title": "The Indian Contract Act, 1872",
  "act_name": "Indian Contract Act",
  "year": 1872,
  "nodes": [ { "node_id": 1, "level": "chapter", "number": "I", "title": "…",
               "children": [ { "node_id": 2, "level": "section", "section_number": "1",
                               "text": "…" } ] } ]
}
```

### 5.4.2 Processed documents (`data/processed/<document_id>.json`)

Written by `src/ingestion/pipeline.py`; per-page text + metadata after OCR/cleaning.
**1632 files** present.

### 5.4.3 Provenance (`data/provenance/<provenance_id>.json`)

Written by `src/llm/provenance.py` and served back by `GET /api/v1/provenance/{id}`.
**271 files** present. Record contains: query, parsed query, retrieved nodes, per-signal
scores, hierarchy paths, citations, counter-authority markers, verification trace,
confidence factors, model/provider metadata, timestamps.

### 5.4.4 Embedding snapshots (`data/embeddings/snapshot_*.json.gz`)

Gzipped dumps produced by `src/embeddings/store.py` for reproducible re-indexing without
recomputing embeddings.

### 5.4.5 Uploads (`data/uploads/`)

Raw uploaded files retained for re-ingestion (2 files present).

---

## 5.5 Redis

Redis 6 is defined as a Compose service (`docker-compose.yml`) and referenced in settings as
an optional cache/queue backing store. **No mandatory runtime dependency on Redis is found in
the application code paths documented here** — treat it as provisioned capacity for caching /
future queueing rather than a hard requirement.

---

## 5.6 Data lifecycle

```text
upload ─► data/uploads/<file>
        ─► data/processed/<doc_id>.json        (ingestion + cleaning)
        ─► data/hierarchy/<doc_id>.json        (hierarchy parse)
        ─► Neo4j / InMemoryGraph               (nodes + PART_OF + CITES)
        ─► Qdrant 4 collections                (embeddings)
        ─► data/embeddings/snapshot_*.json.gz  (optional snapshot)
query   ─► data/provenance/<prov_id>.json      (persisted provenance)
```

Maintenance scripts keep the stores consistent: `scripts/audit_corpus.py` (integrity),
`scripts/corpus_dedup_report.py` (duplicate canonical grouping),
`scripts/prune_stale_artifacts.py` (retention), `scripts/cleanup_provenance.py`.

---

## 5.7 Consistency rules

1. A `document_id` is content-addressed (`src/ingestion/identity.py`) and therefore stable for
   identical input; re-uploading the same file is idempotent.
2. Every Qdrant point's `node_id` must exist as a graph node; the indexer enforces this by
   indexing from the parsed hierarchy.
3. Canonical Act resolution (`canonical.py`) is the single source of truth when multiple
   hierarchy files describe the same Act.
4. Provenance records reference node ids and are immutable once written.
