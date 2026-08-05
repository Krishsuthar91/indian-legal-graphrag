"""Validate hierarchy for common malformations."""

from __future__ import annotations

from src.hierarchy.models import HierarchyNode, HierarchyWarning, ParsedHierarchy


def validate_hierarchy(hierarchy: ParsedHierarchy) -> list[HierarchyWarning]:
    """Run all validation checks and return collected warnings.

    Checks:
    1. Missing parent — a node references a parent_id not in the tree
    2. Duplicate numbering — same numbering at the same level
    3. Broken nesting — a child's level is >= parent's level
    """
    warnings: list[HierarchyWarning] = []
    node_map = {n.node_id: n for n in hierarchy.nodes}

    warnings.extend(_check_missing_parent(hierarchy, node_map))
    warnings.extend(_check_duplicate_numbering(hierarchy))
    warnings.extend(_check_broken_nesting(hierarchy, node_map))

    hierarchy.warnings = warnings
    return warnings


def _check_missing_parent(
    hierarchy: ParsedHierarchy, node_map: dict[str, HierarchyNode]
) -> list[HierarchyWarning]:
    """Detect nodes whose parent_id does not exist in the tree."""
    warnings: list[HierarchyWarning] = []
    for node in hierarchy.nodes:
        if node.parent_id and node.parent_id not in node_map:
            warnings.append(HierarchyWarning(
                warning_type="missing_parent",
                message=f"Node '{node.node_id}' (level {node.level}) references "
                        f"non-existent parent '{node.parent_id}'",
                node_id=node.node_id,
            ))
    return warnings


def _check_duplicate_numbering(hierarchy: ParsedHierarchy) -> list[HierarchyWarning]:
    """Detect duplicate numbering within the same parent."""
    warnings: list[HierarchyWarning] = []
    seen: dict[tuple[str | None, str, int], str] = {}

    for node in hierarchy.nodes:
        if not node.numbering:
            continue
        key = (node.parent_id, node.numbering, node.level)
        if key in seen:
            warnings.append(HierarchyWarning(
                warning_type="duplicate_numbering",
                message=f"Duplicate numbering '{node.numbering}' at level {node.level} "
                        f"under parent '{node.parent_id}' "
                        f"(first: {seen[key]}, duplicate: {node.node_id})",
                node_id=node.node_id,
            ))
        else:
            seen[key] = node.node_id

    return warnings


def _check_broken_nesting(
    hierarchy: ParsedHierarchy, node_map: dict[str, HierarchyNode]
) -> list[HierarchyWarning]:
    """Detect children whose level is >= their parent's level."""
    warnings: list[HierarchyWarning] = []
    for node in hierarchy.nodes:
        if not node.parent_id:
            continue
        parent = node_map.get(node.parent_id)
        if parent and node.level <= parent.level:
            warnings.append(HierarchyWarning(
                warning_type="broken_nesting",
                message=f"Node '{node.node_id}' (level {node.level}) is a child of "
                        f"'{parent.node_id}' (level {parent.level}) — "
                        f"child level must be < parent level",
                node_id=node.node_id,
            ))
    return warnings
