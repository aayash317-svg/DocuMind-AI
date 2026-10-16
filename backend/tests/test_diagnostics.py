from backend.app.ingestion.models import ExtractedDocument, DocumentPage
from backend.app.ingestion.diagnostics import diagnostic_analyzer


def test_document_limitations_and_scanned_page_detection():
    # Document with a low-text page (e.g. potential diagram/scan) and table markers
    pages = [
        DocumentPage(page_number=1, text="Comprehensive introduction to the technical system with many paragraphs and detailed descriptions."),
        DocumentPage(page_number=2, text="Diagram 1."),  # Only 2 words -> potential scan/diagram!
        DocumentPage(page_number=3, text="Name | Type | Value\n-----|------|------\nAlpha | Float | 0.95\nBeta | Int | 100"),  # Table
    ]

    doc = ExtractedDocument(
        document_id="doc_diag_test",
        filename="system_spec.pdf",
        file_type="pdf",
        total_pages=3,
        pages=pages
    )

    limitations = diagnostic_analyzer.analyze(doc, file_size_bytes=1024 * 1024)
    assert limitations.format_name == "PDF"
    assert any("Scanned PDFs" in lim for lim in limitations.limitations)
    assert any("p.2" in risk for risk in limitations.detected_risks)  # Page 2 flagged
    assert any("p.3" in risk for risk in limitations.detected_risks)  # Page 3 table flagged

