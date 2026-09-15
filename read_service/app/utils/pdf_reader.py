import pymupdf4llm

def get_text(file_path: str) -> str:
    """Check the file type. If file is pdf type use pymupdf4llm to read text from pdf file and output text as markdown, else return empty"""
    file_type = file_path.split(".")[-1].lower()
    if file_type == "pdf":
        return pymupdf4llm.to_markdown(file_path)
    else:
        return ""