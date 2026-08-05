"""Graph schema definitions — node labels, relationship types, and constraints."""

from __future__ import annotations

from enum import Enum


class NodeLabel(str, Enum):
    DOCUMENT = "Document"
    CHAPTER = "Chapter"
    PART = "Part"
    SECTION = "Section"
    CLAUSE = "Clause"
    SCHEDULE = "Schedule"
    CASE = "Case"
    COURT = "Court"
    JUDGE = "Judge"
    LEGAL_CONCEPT = "LegalConcept"
    AMENDMENT = "Amendment"


class RelType(str, Enum):
    PART_OF = "PART_OF"
    CITES = "CITES"
    REFERENCES = "REFERENCES"
    INTERPRETS = "INTERPRETS"
    APPLIES = "APPLIES"
    FOLLOWS = "FOLLOWS"
    DISTINGUISHES = "DISTINGUISHES"
    OVERRULES = "OVERRULES"
    AMENDS = "AMENDS"
    REPEALS = "REPEALS"
    PARALLEL_TRANSLATION_OF = "PARALLEL_TRANSLATION_OF"


# Maps hierarchy node_type to graph NodeLabel
HIERARCHY_TYPE_MAP: dict[str, NodeLabel] = {
    "document": NodeLabel.DOCUMENT,
    "chapter": NodeLabel.CHAPTER,
    "part": NodeLabel.PART,
    "section": NodeLabel.SECTION,
    "sub_section": NodeLabel.SECTION,
    "clause": NodeLabel.CLAUSE,
    "sub_clause": NodeLabel.CLAUSE,
    "explanation": NodeLabel.SECTION,
    "illustration": NodeLabel.SECTION,
    "proviso": NodeLabel.SECTION,
    "schedule": NodeLabel.SCHEDULE,
    "appendix": NodeLabel.SCHEDULE,
    "act_title": NodeLabel.DOCUMENT,
    "preamble": NodeLabel.DOCUMENT,
}


# Cypher statements for indexes and constraints
INDEX_STATEMENTS: list[str] = [
    "CREATE INDEX doc_id IF NOT EXISTS FOR (d:Document) ON (d.document_id)",
    "CREATE INDEX section_num IF NOT EXISTS FOR (s:Section) ON (s.numbering)",
    "CREATE INDEX case_citation IF NOT EXISTS FOR (c:Case) ON (c.citation)",
    "CREATE INDEX court_name IF NOT EXISTS FOR (c:Court) ON (c.name)",
    "CREATE INDEX judge_name IF NOT EXISTS FOR (j:Judge) ON (j.name)",
    "CREATE INDEX concept_name IF NOT EXISTS FOR (lc:LegalConcept) ON (lc.name)",
    "CREATE INDEX amendment_id IF NOT EXISTS FOR (a:Amendment) ON (a.amendment_id)",
]

UNIQUE_CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT doc_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
    "CREATE CONSTRAINT case_unique IF NOT EXISTS FOR (c:Case) REQUIRE c.citation IS UNIQUE",
    "CREATE CONSTRAINT court_unique IF NOT EXISTS FOR (c:Court) REQUIRE c.name IS UNIQUE",
]


def get_cypher_setup() -> list[str]:
    """Return all Cypher statements needed to set up the schema."""
    return UNIQUE_CONSTRAINTS + INDEX_STATEMENTS
