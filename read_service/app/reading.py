"""Database-backed text document reading."""
import os
from contextlib import closing
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PostgreSQLConnection

from app.utils.logging import get_logger
from app.utils.pdf_reader import get_text


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

LOGGER = get_logger(__name__)
DATABASE_NAME = os.getenv("INGESTION_DB_NAME", "rag_ingestion")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
READ_OUTPUT_DIR = Path(os.getenv("READ_OUTPUT_DIR", ""))


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


def process_next_document(file_id: int | None = None) -> dict[str, Any] | None:
    """Read one new document and mark it as read."""
    document = _get_document(file_id)
    file_name = os.path.basename(document["file_path"]) if document else "unknown"
    if document is None:
        return None
    
    LOGGER.info("Reading document id=%s", document["id"])
    READ_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_IMAGE_OUTPUT_DIR = os.path.join(READ_OUTPUT_DIR, "pdf_images",f"{document['id']}_{file_name}")
    os.makedirs(PDF_IMAGE_OUTPUT_DIR, exist_ok=True)
    text = get_text(document["file_path"], PDF_IMAGE_OUTPUT_DIR)
    output_path = READ_OUTPUT_DIR / f"{document['id']}_{file_name}.txt"
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(text)
    _update_document(document["id"], "read")
    LOGGER.info("Read document id=%s output=%s", document["id"], output_path)
    return {
        "document_id": document["id"],
        "file_name": document["file_name"],
        "output_path": str(output_path),
        "status": "read",
    }
