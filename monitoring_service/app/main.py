from typing import Dict

from fastapi import FastAPI

from app.monitor import FileMonitor

app = FastAPI(title="OneDrive Ingestion Folder Monitor")
monitor = FileMonitor()

@app.get("/", response_model=Dict[str, str])
def root() -> Dict[str, str]:
    """Return the application health status."""
    return {"message": "Fast API application is running. Status is healthy."}

@app.on_event("startup")
def start_monitor() -> None:
    monitor.start()


@app.on_event("shutdown")
def stop_monitor() -> None:
    monitor.stop()


@app.get("/health")
def health() -> dict:
    return monitor.health()


@app.get("/files")
def files() -> dict:
    return monitor.status()
