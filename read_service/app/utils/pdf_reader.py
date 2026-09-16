import pymupdf4llm
from app.utils.logging import get_logger

LOGGER = get_logger(__name__)

def get_text(file_path: str, image_output_dir: str) -> str:
    """Check the file type. If file is pdf type use pymupdf4llm to read text from pdf file and output text as markdown, else return empty"""
    LOGGER.debug("Getting text from file: %s", file_path)
    file_type = file_path.split(".")[-1].lower()
    if file_type == "pdf":
        LOGGER.debug("Processing PDF file: %s", file_path)
        return pymupdf4llm.to_markdown(file_path, write_images=True, image_path=image_output_dir)
    else:
        LOGGER.warning("Unsupported file type: %s", file_type)
        return ""