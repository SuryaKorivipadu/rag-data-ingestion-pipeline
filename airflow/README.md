# Airflow orchestration

This directory contains the Airflow DAG that coordinates the RAG ingestion services.

## Structure

- `dags/rag_ingestion_dag.py`: detects files and calls chunking, embedding, and vector-ingestion APIs.
- `docker-compose.yml`: local Airflow scheduler, webserver, and PostgreSQL metadata database.
- `.env.example`: API URL configuration.

## Start Airflow

From this directory in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up airflow-init
docker compose up -d
```

Open http://localhost:8080 and sign in with:

- Username: `admin`
- Password: `admin`

The DAG runs every five minutes after it is enabled in the Airflow UI. The default URLs assume the FastAPI services run on the Windows host at ports 8000 through 8003. Change `.env` when the services use different ports or hostnames.

## Stop Airflow

```powershell
docker compose down
```

The current monitor returns all files from its in-memory `/files` endpoint. Until it exposes durable statuses such as `new`, `processing`, and `completed`, the same file can be detected again on later DAG runs. Add persistent file state before using this in production.
