import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.ingestion.pipeline import ingestion_pipeline
from backend.app.retrieval.vector_store import vector_store


def ingest_test_docs():
    docs_to_ingest = [
        ("data/sample_docs/audio_processing_and_speech.pdf", "audio_processing_and_speech.pdf"),
        ("data/sample_docs/distributed_systems_architecture.docx", "distributed_systems_architecture.docx"),
        ("docs/DocuMind_AI_Architecture_Workflows.md", "DocuMind_AI_Architecture_Workflows.txt"),
    ]

    for rel_path, filename in docs_to_ingest:
        file_path = project_root / rel_path
        if not file_path.exists():
            print(f"Skipping {file_path}, does not exist.")
            continue

        print(f"Ingesting {filename}...")
        meta = ingestion_pipeline.process_file(file_path, filename)
        print(f"  -> Ingested {filename}: {meta.total_pages} pages, {meta.total_chunks} chunks, doc_id={meta.document_id}")

    docs = vector_store.list_documents()
    print(f"\nTotal documents now indexed in Qdrant: {len(docs)}")
    for d in docs:
        print(f"  - {d['filename']}: {d['total_pages']} pages, {d['total_chunks']} chunks (ID: {d['document_id']})")


if __name__ == "__main__":
    ingest_test_docs()

