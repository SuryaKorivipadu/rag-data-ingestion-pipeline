# Read service

FastAPI service for reading documents for the RAG pipeline.

The service selects a document with `status = 'new'` from the PostgreSQL `documents` table, reads `.txt` files,+ and updates the document status to `read`.

## Configuration

Create `read_service/.env` locally:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
INGESTION_DB_NAME=rag_ingestion
CHUNKS_OUTPUT_DIR=C:\\Users\\Surya\\OneDrive\\data\\chunks
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
LOG_LEVEL=INFO
LOG_PATH=logs
```

## Run locally

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health check: http://127.0.0.1:8000/health

Process the oldest new text document:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/documents/chunk
```

Process a specific document by database ID:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/documents/chunk?file_id=1"
```

File text is written as `<document_id>_<document_name>.txt` in `READ_OUTPUT_DIR`.
