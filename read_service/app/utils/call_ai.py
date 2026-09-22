import ollama
from typing import Optional
from app.utils.logging import get_logger


LOGGER = get_logger(__name__)


def call_ollama(prompt: str, image_path: Optional[str] = None) -> str:
    """Call the Ollama API with the given prompt and optional image path."""
    model = "qwen2.5vl:3b"
    LOGGER.debug("Calling Ollama model=%s image_path=%s", model, image_path)

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_path],
                }
            ],
        )
        content = response["message"]["content"]
        LOGGER.debug("Ollama call completed model=%s response_length=%d", model, len(content))
        return content
    except Exception as e:
        LOGGER.exception("Ollama call failed model=%s image_path=%s, exception=%s", model, image_path, str(e))
        raise