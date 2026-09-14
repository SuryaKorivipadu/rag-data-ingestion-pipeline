import json
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException

from app.db.models import UserAnswer
from app.api import api
from app.utils.logging import get_logger

app = FastAPI()
logger = get_logger(__name__)


def _log_data_error(operation: str) -> None:
    """Log expected data-source failures without exposing internal details."""
    logger.exception("Data error while attempting to %s", operation)


@app.get("/", response_model=Dict[str, str])
def root() -> Dict[str, str]:
    """Return the application health status."""
    return {"message": "Fast API application is running. Status is healthy."}


@app.get("/user")
def read_user() -> List[Dict[str, Any]]:
    """Return all users from the configured data source."""
    try:
        return api.read_user()
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        # Keep file-system and JSON details out of responses sent to clients.
        _log_data_error("read users")
        raise HTTPException(status_code=500, detail="User data is unavailable")


@app.get("/question/{position}")
def read_questions(position: int) -> Dict[str, Any]:
    """Return the question at the requested position."""
    logger.debug("Reading question at position %s", position)

    try:
        question = api.read_questions(position)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        _log_data_error("read question")
        raise HTTPException(status_code=500, detail="Question data is unavailable")

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return question


@app.get("/alternatives/{question_id}")
def read_alternatives(question_id: int) -> List[Dict[str, Any]]:
    """Return all alternatives belonging to a question."""
    try:
        alternatives = api.read_alternatives(question_id)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        _log_data_error("read alternatives")
        raise HTTPException(status_code=500, detail="Alternative data is unavailable")

    if not alternatives:
        raise HTTPException(status_code=404, detail="Alternatives not found")

    return alternatives


@app.post("/answer", status_code=201)
def create_answer(payload: UserAnswer) -> str:
    """Accept answers and return a confirmation message."""
    # The service reads the first answer, so reject an empty collection early.
    if not payload.answers:
        raise HTTPException(status_code=422, detail="At least one answer is required")

    logger.info("Creating answer for user_id %s", payload.user_id)

    try:
        return api.create_answer(payload.dict())
    except (KeyError, IndexError, TypeError, ValueError) as error:
        _log_data_error("create answer")
        raise HTTPException(status_code=400, detail="Invalid answer data")


@app.get("/result/{user_id}")
def read_result(user_id: int) -> List[Dict[str, Any]]:
    """Return the result associated with a user ID."""
    try:
        result = api.read_result(user_id)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        _log_data_error("read result")
        raise HTTPException(status_code=500, detail="Result data is unavailable")

    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    return result
