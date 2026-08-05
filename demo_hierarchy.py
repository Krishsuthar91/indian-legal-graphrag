"""Demo: parse a sample legal document and display the hierarchy tree."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from src.ingestion.pipeline import ingest_document
from src.hierarchy.parser import parse_and_save


def create_demo_pdf(output_path: Path) -> Path:
    """Create a realistic Indian legal Act PDF with full hierarchy."""
    c = canvas.Canvas(str(output_path), pagesize=A4)
    w, h = A4

    lines = [
        ("THE INDIAN CONTRACT ACT, 1892", 16),
        ("", 8),
        ("An Act to define and amend the law relating to contracts.", 11),
        ("", 8),
        ("WHEREAS it is expedient to define and amend the law relating to contracts;", 10),
        ("", 8),
        ("PART I — PRELIMINARY", 13),
        ("", 6),
        ("CHAPTER I", 12),
        ("Preliminary", 12),
        ("", 6),
        ("Section 1.", 11),
        ("Short title and commencement.", 11),
        ("(1) This Act may be called the Indian Contract Act, 1892.", 10),
        ("(2) It shall come into force on the first day of July, 1892.", 10),
        ("", 6),
        ("Section 2.", 11),
        ("Definitions.", 11),
        ("In this Act, unless there is anything repugnant in the subject or context,—", 10),
        ('(a) "contract" means an agreement enforceable by law;', 10),
        ('(b) "promise" means a proposal when accepted.', 10),
        ("(i) where the proposal is made,", 10),
        ("(ii) where the acceptance is communicated.", 10),
        ("", 6),
        ("Explanation.—Nothing in this section shall apply to agreements.", 10),
        ("", 6),
        ("Illustration.—A says to B, \"I will sell my house for Rs. 1 lakh.\"", 10),
        ("", 6),
        ("Proviso.—Provided that no suit shall be filed after three years.", 10),
        ("", 6),
        ("CHAPTER II", 12),
        ("Of Contracts", 12),
        ("", 6),
        ("Section 3.", 11),
        ("Communication of proposals.", 11),
        ("(1) The communication of proposals is complete when it reaches the offeree.", 10),
        ("(2) The communication of acceptance is complete as against the proposer", 10),
        ("    when it is put in course of transmission.", 10),
        ("", 6),
        ("Section 4.", 11),
        ("When proposals and acceptances are revoked.", 11),
        ("(a) where the contract provides for revocation,", 10),
        ("(b) where no provision is made.", 10),
        ("", 6),
        ("PART II — PERFORMANCE", 13),
        ("", 6),
        ("CHAPTER III", 12),
        ("Of Performance of Contracts", 12),
        ("", 6),
        ("Section 5.", 11),
        ("Contracts to be performed.", 11),
        ("(1) Promisor must perform the promise.", 10),
        ("(2) Promisee may dispense with performance.", 10),
        ("", 6),
        ("Section 6.", 11),
        ("Effect of refusing performance.", 11),
        ("(a) the promisor refuses to perform,", 10),
        ("(b) the performance becomes impossible.", 10),
        ("", 6),
        ("SCHEDULE", 13),
        ("LIST OF AMENDMENTS", 11),
        ("Section 1 — Amendment of Section 2", 10),
        ("Section 2 — Amendment of Section 3", 10),
    ]

    y = h - 2 * cm
    for text, size in lines:
        if not text:
            y -= size * 0.4
            continue
        if y < 2 * cm:
            c.showPage()
            y = h - 2 * cm
        c.setFont("Helvetica", size)
        c.drawString(2.5 * cm, y, text)
        y -= size * 0.5

    c.save()
    return output_path


def print_tree(h, indent: int = 0, node_id: str = "root", is_last: bool = True):
    """Pretty-print the hierarchy tree using ASCII characters."""
    node_map = {n.node_id: n for n in h.nodes}
    node = node_map.get(node_id)
    if not node:
        return
    if indent == 0:
        prefix = ""
        connector = ""
    else:
        prefix = "|   " * (indent - 1)
        connector = "+-- " if is_last else "|-- "
    label = f"[{node.node_type}] {node.title}" if node.title else f"[{node.node_type}]"
    print(f"{prefix}{connector}{label}")
    for i, child_id in enumerate(node.children):
        is_last_child = i == len(node.children) - 1
        print_tree(h, indent + 1, child_id, is_last_child)


if __name__ == "__main__":
    pdf_path = Path("data/contract_act_sample.pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    create_demo_pdf(pdf_path)
    print(f"Created sample PDF: {pdf_path}\n")

    doc = ingest_document(pdf_path)
    print(f"Ingested: {doc.document_id} ({doc.title})\n")

    hierarchy = parse_and_save(Path(f"data/processed/{doc.document_id}.json"))
    print(f"{'='*60}")
    print(f"HIERARCHY TREE - {hierarchy.document_id}")
    print(f"{'='*60}")
    print_tree(hierarchy)

    print(f"\n{'='*60}")
    print(f"NESTED SET INDEX")
    print(f"{'='*60}")
    node_map = {n.node_id: n for n in hierarchy.nodes}
    for entry in sorted(hierarchy.nested_set, key=lambda e: e.left):
        node = node_map.get(entry.node_id)
        label = f"[{node.node_type}] {node.title}" if node else entry.node_id
        print(f"  L={entry.left:3d}  R={entry.right:3d}  D={entry.depth}  {label}")

    if hierarchy.warnings:
        print(f"\n{'='*60}")
        print(f"WARNINGS ({len(hierarchy.warnings)})")
        print(f"{'='*60}")
        for w in hierarchy.warnings:
            print(f"  [{w.warning_type}] {w.message}")
    else:
        print(f"\nNo hierarchy warnings detected.")
