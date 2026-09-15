from typing import Any

from fastapi import FastAPI, HTTPException, Query
from psycopg2 import Error as PostgreSQLError

from app.reading import process_next_document
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
