"""Airflow DAG for the RAG document ingestion pipeline."""

from datetime import datetime
import os
from typing import Any

import requests
from airflow.decorators import dag, task


MONITOR_URL = os.getenv("MONITOR_URL", "http://host.docker.internal:8000")
CHUNKING_URL = os.getenv("CHUNKING_URL", "http://host.docker.internal:8001")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://host.docker.internal:8002")
VECTOR_INGESTION_URL = os.getenv(
    "VECTOR_INGESTION_URL", "http://host.docker.internal:8003"
)


@dag(
    dag_id="rag_ingestion",
    start_date=datetime(2026, 1, 1),
    schedule="*/5 * * * *",
    catchup=False,
    tags=["rag", "ingestion"],
)
def rag_ingestion():
    """Detect files and process each file through the RAG pipeline."""

    @task
    def detect_files() -> list[dict[str, Any]]:
        """Read files exposed by the monitoring service.

        Replace /files with a durable /files?status=new endpoint when the
        monitoring service persists file state.
        """
        response = requests.get(f"{MONITOR_URL}/files", timeout=30)
        response.raise_for_status()
        payload = response.json()
        return [{"path": path} for path in payload.get("files", [])]

    @task
    def chunk_document(file: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{CHUNKING_URL}/documents/chunk",
            json=file,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    @task
    def embed_chunks(chunks: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{EMBEDDING_URL}/documents/embed",
            json=chunks,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    @task
    def ingest_vectors(embeddings: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{VECTOR_INGESTION_URL}/vectors/ingest",
            json=embeddings,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    files = detect_files()
    chunks = chunk_document.expand(file=files)
    embeddings = embed_chunks.expand(chunks=chunks)
    ingest_vectors.expand(embeddings=embeddings)


rag_ingestion()
