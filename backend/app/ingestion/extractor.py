from pathlib import Path
from typing import List
import re
import pypdf
import docx

from backend.app.ingestion.models import ExtractedDocument, DocumentPage


class DocumentExtractor:
    """Extracts text and page metadata from supported document types."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

    @staticmethod
    def clean_text(text: str) -> str:
        """Strip raw embedded SVG elements, XML vector noise, and excess whitespace."""
        if not text:
            return ""
        # Strip embedded <svg>...</svg> blocks
        cleaned = re.sub(r'<svg[\s\S]*?</svg>', '', text, flags=re.IGNORECASE)
        # Strip standalone <svg> or </svg> tags
        cleaned = re.sub(r'</?svg[^>]*>', '', cleaned, flags=re.IGNORECASE)
        # Normalize multiple spaces
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        return cleaned.strip()

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def extract(cls, file_path: Path, document_id: str, original_filename: str) -> ExtractedDocument:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            pages = cls._extract_pdf(file_path)
        elif ext == ".docx":
            pages = cls._extract_docx(file_path)
        elif ext in {".txt", ".md"}:
            pages = cls._extract_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Supported formats are PDF, DOCX, TXT, MD.")

        # Filter out empty or whitespace-only pages
        valid_pages = [p for p in pages if p.text.strip()]
        if not valid_pages:
            raise ValueError(f"No readable text could be extracted from {original_filename}.")

        return ExtractedDocument(
            document_id=document_id,
            filename=original_filename,
            file_type=ext.lstrip("."),
            total_pages=len(valid_pages),
            pages=valid_pages,
        )

    @classmethod
    def _extract_pdf(cls, file_path: Path) -> List[DocumentPage]:
        pages: List[DocumentPage] = []
        try:
            reader = pypdf.PdfReader(str(file_path))
            for idx, page in enumerate(reader.pages):
                text = cls.clean_text(page.extract_text() or "")
                pages.append(DocumentPage(page_number=idx + 1, text=text))
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {str(e)}") from e
        return pages

    @classmethod
    def _extract_docx(cls, file_path: Path) -> List[DocumentPage]:
        try:
            doc = docx.Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            
            # DOCX does not have native physical page boundaries in raw XML.
            # Group every ~500 words or 3-4 paragraphs into logical pages.
            pages: List[DocumentPage] = []
            current_page_text: List[str] = []
            current_word_count = 0
            page_num = 1

            for p in paragraphs:
                current_page_text.append(p)
                current_word_count += len(p.split())
                if current_word_count >= 400:
                    pages.append(DocumentPage(page_number=page_num, text="\n\n".join(current_page_text)))
                    page_num += 1
                    current_page_text = []
                    current_word_count = 0

            if current_page_text:
                pages.append(DocumentPage(page_number=page_num, text="\n\n".join(current_page_text)))

            return pages
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from DOCX: {str(e)}") from e

    @classmethod
    def _extract_txt(cls, file_path: Path) -> List[DocumentPage]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            pages: List[DocumentPage] = []

            # 1. Check for form feed characters
            if "\f" in content:
                for idx, p in enumerate(content.split("\f")):
                    if p.strip():
                        pages.append(DocumentPage(page_number=idx + 1, text=p.strip()))
                if pages:
                    return pages

            # 2. Markdown heading-based pagination
            ext = file_path.suffix.lower()
            if ext == ".md" or "\n# " in content or "\n## " in content:
                import re
                sections = re.split(r'\n(?=#{1,2}\s+[^\n]+)', content)
                page_num = 1
                for s in sections:
                    s_clean = s.strip()
                    if s_clean:
                        pages.append(DocumentPage(page_number=page_num, text=s_clean))
                        page_num += 1
                if pages:
                    return pages

            # 3. Plain text paragraph chunking into logical pages of ~400 words
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            current_page_text: List[str] = []
            current_word_count = 0
            page_num = 1

            for p in paragraphs:
                current_page_text.append(p)
                current_word_count += len(p.split())
                if current_word_count >= 400:
                    pages.append(DocumentPage(page_number=page_num, text="\n\n".join(current_page_text)))
                    page_num += 1
                    current_page_text = []
                    current_word_count = 0

            if current_page_text:
                pages.append(DocumentPage(page_number=page_num, text="\n\n".join(current_page_text)))

            if not pages and content.strip():
                pages.append(DocumentPage(page_number=1, text=content.strip()))

            return pages
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from text file: {str(e)}") from e

