from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.ingestion.models import ExtractedDocument


class DocumentLimitations(BaseModel):
    """Explains technical limitations of the document format and extraction caveats."""
    format_name: str
    limitations: List[str]
    detected_risks: List[str] = Field(default_factory=list)
    querying_advice: List[str] = Field(default_factory=list)


FORMAT_LIMITATIONS = {
    "pdf": [
        "Scanned PDFs: Text within image-based or scanned PDFs requires OCR. Blurry scans cause extraction typos.",
        "Complex tables: Multi-column tables and aligned numbers may lose row/column structural coordinates.",
        "Images and diagrams: Charts, flowcharts, and schematics cannot be interpreted without vision models.",
        "Password protection: Encrypted or DRM-protected PDFs will fail parsing."
    ],
    "docx": [
        "Headers and footers: Repeating page headers and footers can cause duplicated text chunks.",
        "Floating text boxes: Text boxes and shapes outside the main body flow may be extracted out of order.",
        "Embedded spreadsheets: Complex nested tables and equations may lose layout alignment.",
        "Track changes & comments: Hidden markup or rejected revisions can introduce noise."
    ],
    "txt": [
        "Absence of rich structure: Plain text lacks bolding, font hierarchies, headings, and physical page breaks.",
        "Formatted tables: ASCII tables may become distorted when line-wrapped during chunking."
    ],
    "md": [
        "Markdown syntax: Raw code blocks or complex HTML tags may consume chunk context budget.",
        "Unrendered embeds: Embedded image links cannot be viewed or analyzed."
    ]
}

GENERAL_LIMITATIONS = [
    "Large documents: Files over 50 pages require more retrieval steps to gather distributed evidence.",
    "Unsupported questions: The model strictly refuses to guess if facts are omitted from the document."
]


class DocumentDiagnosticAnalyzer:
    """Analyzes extracted documents to surface format-specific limitations and extraction anomalies."""

    @classmethod
    def analyze(cls, extracted_doc: ExtractedDocument, file_size_bytes: int) -> DocumentLimitations:
        file_type = extracted_doc.file_type.lower()
        format_name = file_type.upper()

        limitations = list(FORMAT_LIMITATIONS.get(file_type, [])) + GENERAL_LIMITATIONS
        detected_risks = []
        advice = [
            "Ask specific questions citing names, numbers, or section headings for best retrieval.",
            "If asking about visual diagrams, ensure text captions or descriptions exist in the document.",
            "Verify citations using the page badges provided with each answer."
        ]

        # Diagnostic checks across extracted pages
        low_text_pages = []
        table_like_pages = []

        for p in extracted_doc.pages:
            text = p.text.strip()
            word_count = len(text.split())

            # Check 1: Potential scanned image / diagram page
            if word_count < 25 and word_count > 0:
                low_text_pages.append(p.page_number)

            # Check 2: Potential table content
            if text.count("|") > 4 or text.count("\t") > 6:
                table_like_pages.append(p.page_number)

        if low_text_pages:
            pages_str = ", ".join(f"p.{p}" for p in low_text_pages[:4])
            if len(low_text_pages) > 4:
                pages_str += f" (+{len(low_text_pages) - 4} more)"
            detected_risks.append(
                f"Low text density detected on {pages_str}. These pages may contain diagrams, charts, or scans that standard text extraction cannot read."
            )

        if table_like_pages:
            pages_str = ", ".join(f"p.{p}" for p in table_like_pages[:3])
            detected_risks.append(
                f"Table formatting detected on {pages_str}. Multi-column row structures may have been flattened into sequential lines."
            )

        if file_size_bytes > 5 * 1024 * 1024:
            detected_risks.append("Large file (>5 MB): Retrieval uses top-k ranking; cross-document questions may take an extra step.")

        return DocumentLimitations(
            format_name=format_name,
            limitations=limitations,
            detected_risks=detected_risks,
            querying_advice=advice
        )


diagnostic_analyzer = DocumentDiagnosticAnalyzer()

