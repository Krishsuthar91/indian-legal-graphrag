"""Pydantic models for the legal hierarchy tree."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HierarchyNode(BaseModel):
    """A single node in the legal hierarchy tree."""

    node_id: str
    parent_id: str | None = None
    level: int
    node_type: str  # act_title, preamble, part, chapter, section, sub_section,
    # clause, sub_clause, explanation, illustration, proviso,
    # schedule, appendix, document
    title: str = ""
    text: str = ""
    start_page: int = 1
    end_page: int = 1
    numbering: str = ""  # raw numbering text, e.g. "Section 12", "(a)", "(i)"
    children: list[str] = Field(default_factory=list)  # child node_ids


class NestedSetEntry(BaseModel):
    """Nested Set Index entry for a node."""

    node_id: str
    left: int
    right: int
    depth: int


class HierarchyWarning(BaseModel):
    """A warning about malformed hierarchy."""

    warning_type: str  # missing_parent, duplicate_numbering, broken_nesting
    message: str
    node_id: str = ""


class ParsedHierarchy(BaseModel):
    """Complete parsed hierarchy for a document."""

    document_id: str
    root_id: str
    nodes: list[HierarchyNode]
    nested_set: list[NestedSetEntry]
    warnings: list[HierarchyWarning]
