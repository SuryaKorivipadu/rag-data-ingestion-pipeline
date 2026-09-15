"""Database-backed text document chunking."""

import json
import os
from contextlib import closing
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from psycopg2.extensions import connection as PostgreSQLConnection

from app.utils.logging import get_logger


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

LOGGER = get_logger(__name__)
DATABASE_NAME = os.getenv("INGESTION_DB_NAME", "rag_ingestion")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
CHUNKS_OUTPUT_DIR = Path(
    os.getenv("CHUNKS_OUTPUT_DIR", r"C:\Users\Surya\OneDrive\data\chunks")
)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))


def get_connection(database: str = DATABASE_NAME) -> PostgreSQLConnection:
    """Open a PostgreSQL connection using service configuration."""
    if not POSTGRES_USER or not POSTGRES_PASSWORD:
        raise RuntimeError("POSTGRES_USER and POSTGRES_PASSWORD must be configured")
    try:
        port = int(POSTGRES_PORT)
    except ValueError as error:
        raise ValueError("POSTGRES_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("POSTGRES_PORT must be between 1 and 65535")
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=port,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=database,
    )


def _get_document(file_id: int | None) -> dict[str, Any] | None:
    """Return one new document, optionally restricted to an ID."""
    query = """
        SELECT id, file_path, file_name, file_hash
        FROM documents
        WHERE status = 'new'
          AND (%s IS NULL OR id = %s)
        ORDER BY discovered_at, id
        LIMIT 1
    """
    with closing(get_connection()) as database_connection:
        with database_connection.cursor() as cursor:
            cursor.execute(query, (file_id, file_id))
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "file_path": row[1],
        "file_name": row[2],
        "file_hash": row[3],
    }


def _update_document(
    document_id: int,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update document status and clear or record the latest error."""
    query = """
        UPDATE documents
        SET status = %s, error_message = %s, updated_at = NOW(),
            completed_at = CASE WHEN %s = 'ingested' THEN NOW() ELSE completed_at END
        WHERE id = %s
    """
    with closing(get_connection()) as database_connection:
        try:
            with database_connection.cursor() as cursor:
                cursor.execute(query, (status, error_message, status, document_id))
            database_connection.commit()
        except psycopg2.Error:
            database_connection.rollback()
            raise


def _write_chunks(document: dict[str, Any], chunks: list[str]) -> Path:
    """Write chunk data to a UTF-8 JSON file and return its path."""
    CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHUNKS_OUTPUT_DIR / f"{document['id']}_{document['file_hash']}.json"
    payload = {
        "document_id": document["id"],
        "file_name": document["file_name"],
        "file_path": document["file_path"],
        "chunks": [
            {"chunk_id": index, "text": text}
            for index, text in enumerate(chunks)
        ],
    }
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
    return output_path


def process_next_document(file_id: int | None = None) -> dict[str, Any] | None:
    """Chunk one new text document and mark it as chunked."""
    if CHUNK_SIZE <= 0 or CHUNK_OVERLAP < 0 or CHUNK_OVERLAP >= CHUNK_SIZE:
        raise ValueError("CHUNK_SIZE must be positive and CHUNK_OVERLAP must be smaller")

    document = _get_document(file_id)
    if document is None:
        return None

    source_path = Path(document["file_path"])
    if source_path.suffix.lower() != ".txt":
        raise ValueError(f"Document {document['id']} is not a .txt file")
    if not source_path.is_file():
        raise FileNotFoundError(f"Document file does not exist: {source_path}")

    LOGGER.info("Reading document id=%s", document["id"])
    text = source_path.read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_text(text)
    output_path = _write_chunks(document, chunks)
    _update_document(document["id"], "chunked")
    LOGGER.info(
        "Chunked document id=%s chunks=%s output=%s",
        document["id"],
        len(chunks),
        output_path,
    )
    return {
        "document_id": document["id"],
        "file_name": document["file_name"],
        "chunk_count": len(chunks),
        "output_path": str(output_path),
        "status": "chunked",
    }
