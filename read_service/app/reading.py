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
from app.utils.call_ai import call_ollama


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

LOGGER = get_logger(__name__)
DATABASE_NAME = os.getenv("INGESTION_DB_NAME", "rag_ingestion")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
READ_OUTPUT_DIR = Path(os.getenv("READ_OUTPUT_DIR", ""))
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


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


def _get_document(file_id: int,status: str = "new",) -> dict[str, Any] | None:
    """Return one document with the requested processing status."""
    query = """
        SELECT id, file_path, file_name, file_hash
        FROM documents
        WHERE status = %s
        AND id = %s
        ORDER BY discovered_at, id
        LIMIT 1
    """
    with closing(get_connection()) as database_connection:
        with database_connection.cursor() as cursor:
            cursor.execute(query, (status, file_id))
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


def create_image_jobs(document_id: int) -> dict[str, Any]:
    """Create one durable image job for each extracted document image."""
    document = _get_document(document_id, status="read")
    if document is None:
        raise FileNotFoundError(
            f"Read document {document_id} was not found"
        )
    file_name = os.path.basename(document["file_path"]) if document else "unknown"
    with closing(get_connection()) as database_connection:
        with database_connection.cursor() as cursor:
            image_directory = os.path.join(READ_OUTPUT_DIR, "pdf_images",f"{document['id']}_{file_name}")

            if not image_directory.is_dir():
                raise FileNotFoundError(
                    f"Image directory does not exist: {image_directory}"
                )

            image_files = sorted(
                path
                for path in image_directory.iterdir()
                if path.is_file()
                and path.suffix.lower() in IMAGE_EXTENSIONS
            )

            image_job_ids = []
            insert_query = """
                INSERT INTO image_jobs (
                    document_id,
                    image_name,
                    image_path,
                    status
                )
                VALUES (%s, %s, %s, 'pending')
                ON CONFLICT (document_id, image_name)
                DO UPDATE SET image_path = EXCLUDED.image_path
                RETURNING id
            """

            for image_path in image_files:
                cursor.execute(
                    insert_query,
                    (
                        document_id,
                        image_path.name,
                        str(image_path),
                    ),
                )
                image_job_ids.append(cursor.fetchone()[0])

            images_status = "pending" if image_files else "completed"

            cursor.execute(
                """
                UPDATE documents
                SET images_status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (images_status, document_id),
            )

        database_connection.commit()

    LOGGER.info(
        "Created image jobs document_id=%s count=%s",
        document_id,
        len(image_files),
    )

    return {
        "document_id": document_id,
        "image_job_count": len(image_files),
        "image_job_ids": image_job_ids,
        "images_status": images_status,
    }


def process_image_job(image_job_id: int) -> dict[str, Any]:
    """Describe one image with Ollama and mark its job as completed."""
    with closing(get_connection()) as database_connection:
        with database_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, document_id, image_name, image_path, status
                FROM image_jobs
                WHERE id = %s
                """,
                (image_job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"Image job {image_job_id} was not found")
            image_job = {
                "id": row[0],
                "document_id": row[1],
                "image_name": row[2],
                "image_path": row[3],
                "status": row[4],
            }

    image_path = Path(image_job["image_path"])
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file does not exist: {image_path}")

    # check status of image_job here? if it's already completed or failed, should we skip processing?
    if image_job["status"] == "completed":
        LOGGER.info("Image job %s is already completed", image_job_id)
        return {
            "image_job_id": image_job_id,
            "document_id": image_job["document_id"],
            "image_name": image_job["image_name"],
            "description": image_job["description"],
            "status": "completed",
        }
    elif image_job["status"] == "failed":
        raise RuntimeError(f"Image job {image_job_id} has failed")

    prompt = f"Describe the content of the image at {image_path}."
    try:
        description = call_ollama(prompt, str(image_path))
    except Exception as error:
        LOGGER.exception("Failed to describe image job id=%s", image_job_id)
        with closing(get_connection()) as database_connection:
            with database_connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE image_jobs
                    SET status = 'failed', error_message = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (str(error), image_job_id),
                )
            database_connection.commit()
        raise

    with closing(get_connection()) as database_connection:
        with database_connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE image_jobs
                SET status = 'completed', description = %s,
                    error_message = NULL, updated_at = NOW()
                WHERE id = %s
                """,
                (description, image_job_id),
            )
        database_connection.commit()

    LOGGER.info(
        "Processed image job id=%s document_id=%s",
        image_job_id,
        image_job["document_id"],
    )

    return {
        "image_job_id": image_job_id,
        "document_id": image_job["document_id"],
        "image_name": image_job["image_name"],
        "description": description,
        "status": "completed",
    }


def assemble_document(document_id: int) -> dict[str, Any]:
    """Assemble the text and image descriptions for a document."""
    document = _get_document(document_id, status="read")
    if document is None:
        raise FileNotFoundError(
            f"Read document {document_id} was not found"
        )
    file_name = os.path.basename(document["file_path"]) if document else "unknown"
    with closing(get_connection()) as database_connection:
        with database_connection.cursor() as cursor:
            # Get the text content
            text_file_path = READ_OUTPUT_DIR / f"{document['id']}_{file_name}.txt"
            if not text_file_path.is_file():
                raise FileNotFoundError(f"Text file does not exist: {text_file_path}")
            with open(text_file_path, "r", encoding="utf-8") as text_file:
                text_content = text_file.read()

            # Get the image descriptions
            cursor.execute(
                """
                SELECT image_name, image_path, description
                FROM image_jobs
                WHERE document_id = %s AND status = 'completed'
                """,
                (document_id,),
            )
            image_jobs = cursor.fetchall()

    image_descriptions = {}
    for image_name, image_path, description in image_jobs:
        normalized_image_path = str(image_path).replace("\\", "/")
        markdown_image = f"![]({normalized_image_path})"
        replacement = f"### Image: {image_name}\n\n{description or ''}"
        if markdown_image in text_content:
            text_content = text_content.replace(markdown_image, replacement, 1)
        else:
            LOGGER.warning(
                "Image reference not found in document text: %s",
                image_path,
            )
            text_content += f"\n\n{replacement}"
        image_descriptions[image_name] = description

    assembled_content = {
        "document_id": document_id,
        "file_name": document["file_name"],
        "text_content": text_content,
        "image_descriptions": image_descriptions,
    }

    ## Update the document status to 'assembled'
    _update_document(document_id, "assembled")

    LOGGER.info(
        "Assembled document id=%s with %d images",
        document_id,
        len(image_descriptions),
    )

    return assembled_content