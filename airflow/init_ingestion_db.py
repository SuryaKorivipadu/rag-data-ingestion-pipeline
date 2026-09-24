"""Create the RAG application database and document tracking table."""

import os
import re
from contextlib import closing
from pathlib import Path
from typing import Final

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extensions import connection as PostgreSQLConnection

from utils.logging import get_logger


load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)

LOGGER = get_logger(__name__)
DATABASE_NAME: Final[str] = os.getenv("INGESTION_DB_NAME", "rag_ingestion")
POSTGRES_HOST: Final[str] = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT_VALUE: Final[str] = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER: Final[str] = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD: Final[str] = os.getenv("POSTGRES_PASSWORD", "")


def connection(database: str) -> PostgreSQLConnection:
    """Open a PostgreSQL connection using environment configuration."""
    if not POSTGRES_USER or not POSTGRES_PASSWORD:
        raise RuntimeError(
            "POSTGRES_USER and POSTGRES_PASSWORD must be set before running "
            "the database bootstrap script"
        )
    try:
        postgres_port = int(POSTGRES_PORT_VALUE)
    except ValueError as error:
        raise ValueError("POSTGRES_PORT must be an integer") from error

    if not 1 <= postgres_port <= 65535:
        raise ValueError("POSTGRES_PORT must be between 1 and 65535")

    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=postgres_port,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=database,
    )


def validate_database_name(name: str) -> None:
    """Reject database names that are unsafe as SQL identifiers."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid database name: {name!r}")


def create_database() -> None:
    """Create the application database when it does not already exist."""
    validate_database_name(DATABASE_NAME)
    with closing(connection("postgres")) as admin_connection:
        # CREATE DATABASE must execute outside a transaction.
        admin_connection.autocommit = True
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (DATABASE_NAME,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(DATABASE_NAME)
                    )
                )
                LOGGER.info("Created database %s", DATABASE_NAME)
            else:
                LOGGER.info("Database already exists: %s", DATABASE_NAME)


def create_documents_table() -> None:
    """Create the document tracking table when it does not exist."""
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS documents (
            id BIGSERIAL PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'new',
            images_status TEXT NOT NULL DEFAULT 'not_started',
            CONSTRAINT documents_status_check
                CHECK (status IN ('new', 'read', 'chunked', 'embedded', 'ingested')),
            CONSTRAINT documents_images_status_check
                CHECK (images_status IN (
                    'not_started',
                    'pending',
                    'processing',
                    'completed',
                    'failed'
                )),
            error_message TEXT,
            discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """
    with connection(DATABASE_NAME) as database_connection:
        with database_connection.cursor() as cursor:
            cursor.execute(create_table_sql)
        database_connection.commit()
    LOGGER.info("Ensured documents table exists in database %s", DATABASE_NAME)


def create_image_jobs_table() -> None:
    """Create the image processing table when it does not exist."""
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS image_jobs (
            id BIGSERIAL PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents(id),
            image_name TEXT NOT NULL,
            image_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            CONSTRAINT image_jobs_status_check
                CHECK (status IN (
                    'pending',
                    'processing',
                    'completed',
                    'failed'
                )),
            description TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (document_id, image_name)
        )
    """
    with connection(DATABASE_NAME) as database_connection:
        with database_connection.cursor() as cursor:
            cursor.execute(create_table_sql)
        database_connection.commit()
    LOGGER.info("Ensured image_jobs table exists in database %s", DATABASE_NAME)


def main() -> None:
    """Create the application database and its document tracking table."""
    create_database()
    create_documents_table()
    create_image_jobs_table()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, psycopg2.Error):
        LOGGER.exception("Database initialization failed")
        raise SystemExit(1) from None
