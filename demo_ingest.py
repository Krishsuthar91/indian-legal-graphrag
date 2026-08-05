"""Demo script: create a sample legal PDF and run the ingestion pipeline."""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def create_sample_legal_pdf(output_path: Path) -> Path:
    """Generate a realistic Indian legal judgment PDF for testing."""
    c = canvas.Canvas(str(output_path), pagesize=A4)
    w, h = A4

    lines = [
        ("IN THE HIGH COURT OF KARNATAKA", 14),
        ("BENGALURU BENCH", 12),
        ("", 10),
        ("WRIT PETITION NO. 4567 OF 2024", 12),
        ("", 10),
        ("Petitioner:  Ramesh Kumar", 11),
        ("Respondent:  State of Karnataka", 11),
        ("", 10),
        ("JUDGMENT", 14),
        ("", 10),
        ("Before the Hon'ble Mr. Justice R. Venkatesh", 11),
        ("", 10),
        ("Date of Judgment: 15th March, 2024", 11),
        ("", 10),
        (
            "This writ petition has been filed under Article 226 of the "
            "Constitution of India seeking a writ of certiorari to quash "
            "the order dated 10th January, 2024 passed by the Deputy "
            "Commissioner, Bengaluru Urban District.",
            11,
        ),
        ("", 10),
        (
            "Section 123 of the Indian Contract Act, 1872 provides that "
            "an agreement without consideration is void, unless it is "
            "expressed in writing and registered under the law for the "
            "time being in force.",
            11,
        ),
        ("", 10),
        (
            "Order VII Rule 11 of the Code of Civil Procedure, 1908 "
            "empowers the court to reject a plaint where it does not "
            "disclose a cause of action.",
            11,
        ),
        ("", 10),
        (
            "Article 14 of the Constitution of India guarantees equality "
            "before the law and equal protection of the laws within the "
            "territory of India. The State shall not deny to any person "
            "equality before the law.",
            11,
        ),
        ("", 10),
        (
            "Having considered the submissions of both parties and the "
            "materials on record, this Court is of the opinion that the "
            "impugned order is liable to be quashed.",
            11,
        ),
        ("", 10),
        (
            "In the result, the writ petition is allowed. The impugned "
            "order dated 10th January, 2024 is hereby quashed.",
            11,
        ),
        ("", 10),
        ("Sd/-", 11),
        ("Justice R. Venkatesh", 11),
        ("Bengaluru", 10),
        ("Dated: 15th March, 2024", 10),
        ("Page 1 of 1", 9),
        ("Downloaded from Indian Kanoon", 9),
    ]

    y = h - 2 * cm
    for text, size in lines:
        if not text:
            y -= size * 0.3
            continue
        c.setFont("Helvetica", size)
        c.drawString(2.5 * cm, y, text)
        y -= size * 0.45

    c.save()
    return output_path


if __name__ == "__main__":
    from src.ingestion.pipeline import ingest_document

    pdf_path = Path("data/sample_legal_judgment.pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    create_sample_legal_pdf(pdf_path)
    print(f"Created sample PDF: {pdf_path}")

    doc = ingest_document(pdf_path)
    print(f"\nIngested document:")
    print(f"  ID:       {doc.document_id}")
    print(f"  Title:    {doc.title}")
    print(f"  Language: {doc.language}")
    print(f"  Pages:    {len(doc.pages)}")
    print(f"  Scanned:  {doc.metadata.is_scanned}")
    print(f"  Output:   data/processed/{doc.document_id}.json")
