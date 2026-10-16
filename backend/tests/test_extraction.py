import tempfile
from pathlib import Path
import pytest
from backend.app.ingestion.extractor import DocumentExtractor
from backend.app.ingestion.chunker import DocumentChunker


def test_txt_extraction_and_chunking():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Line 1 of text.\n\nLine 2 with detailed explanation of architecture.")
        temp_path = Path(f.name)

    try:
        doc = DocumentExtractor.extract(temp_path, "doc_test_1", "sample.txt")
        assert doc.document_id == "doc_test_1"
        assert doc.filename == "sample.txt"
        assert doc.file_type == "txt"
        assert doc.total_pages >= 1

        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1
        assert chunks[0].document_id == "doc_test_1"
        assert chunks[0].filename == "sample.txt"
        assert chunks[0].page_number == 1
        assert "sample.txt" in chunks[0].metadata["filename"]
    finally:
        temp_path.unlink(missing_ok=True)


def test_unsupported_file_extension():
    fake_path = Path("fake_document.xyz")
    with pytest.raises(ValueError, match="Unsupported file format"):
        DocumentExtractor.extract(fake_path, "doc_unsupported", "fake.xyz")

