import json
import os
from typing import Any, Dict, List, Optional

from app.utils.logging import get_logger


DATA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'data')
)
logger = get_logger(__name__)


def _load_json(filename: str) -> Any:
    """Load a JSON file from the application's data directory."""
    file_path = os.path.join(DATA_PATH, filename)

    # Keep file encoding explicit for non-ASCII data.
    with open(file_path, encoding='utf-8') as file:
        return json.load(file)


def read_user() -> List[Dict[str, Any]]:
    """Return all users from the data file."""
    logger.debug('Reading users')
    return _load_json('users.json')


def read_questions(position: int) -> Optional[Dict[str, Any]]:
    """Return the question at the requested position, if it exists."""
    logger.debug('Reading question at position %s', position)
    questions = _load_json('questions.json')

    for question in questions:
        if question['position'] == position:
            return question

    return None


def read_alternatives(question_id: int) -> List[Dict[str, Any]]:
    """Return alternatives belonging to the requested question."""
    logger.debug('Reading alternatives for question_id %s', question_id)
    question_alternatives = []
    alternatives = _load_json('alternatives.json')

    for alternative in alternatives:
        if alternative['question_id'] == question_id:
            question_alternatives.append(alternative)

    return question_alternatives


def create_answer(payload: Dict[str, Any]) -> str:
    """Return a confirmation message for the submitted answer."""
    logger.debug('Creating answer for user_id %s', payload['user_id'])
    return (
        f"Received answer for user_id: {payload['user_id']} and "
        f"question_id: {payload['answers'][0]['question_id']}."
    )


def read_result(user_id: int) -> List[Dict[str, Any]]:
    """Return the result data for the requested user."""
    logger.debug('Reading result for user_id %s', user_id)
    user_result = []

    results = _load_json('results.json')
    users = _load_json('users.json')
    cars = _load_json('cars.json')

    for result in results:
        if result['user_id'] == user_id:
            for user in users:
                if user['id'] == result['user_id']:
                    user_result.append({'user': user})
                    break

        for car_id in result['cars']:
            for car in cars:
                if car_id == car['id']:
                    user_result.append(car)

    return user_result
