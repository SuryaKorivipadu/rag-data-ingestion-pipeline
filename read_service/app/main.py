from typing import Any

from fastapi import FastAPI, HTTPException, Query
from psycopg2 import Error as PostgreSQLError

from app.reading import create_image_jobs, process_next_document, process_image_job, assemble_document
from app.utils.logging import get_logger

app = FastAPI(title="Read Service")
LOGGER = get_logger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "healthy"}


@app.post("/documents/read")
def read_document(
    file_id: int | None = Query(default=None, gt=0),
) -> dict[str, Any]:
    """Read one new text document selected from the ingestion database."""
    try:
        result = process_next_document(file_id)
    except (FileNotFoundError, OSError, ValueError) as error:
        LOGGER.warning("Document reading failed: %s", error)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (PostgreSQLError, RuntimeError) as error:
        LOGGER.exception("Unexpected document reading failure")
        raise HTTPException(
            status_code=500,
            detail="Document reading failed",
        ) from error

    if result is None:
        raise HTTPException(status_code=404, detail="No new document is available")
    return result


@app.post("/documents/{document_id}/image-jobs")
def create_document_image_jobs(document_id: int) -> dict[str, Any]:
    try:
        return create_image_jobs(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PostgreSQLError as error:
        LOGGER.exception(
            "Failed to create image jobs document_id=%s",
            document_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not create image jobs",
        ) from error


@app.post("/image-jobs/{image_job_id}/process")
def process_document_image_job(image_job_id: int) -> dict[str, Any]:
    try:
        return process_image_job(image_job_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PostgreSQLError as error:
        LOGGER.exception(
            "Failed to process image_job_id=%s",
            image_job_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not process image job",
        ) from error


@app.post("/documents/{document_id}/assemble")
def assemble_document_text(document_id: int) -> dict[str, Any]:
    try:
        return assemble_document(document_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (OSError, PostgreSQLError) as error:
        LOGGER.exception(
            "Failed to assemble document_id=%s",
            document_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not assemble document",
        ) from error