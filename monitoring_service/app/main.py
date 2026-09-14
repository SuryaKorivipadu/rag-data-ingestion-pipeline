from typing import Dict
from fastapi import FastAPI
from app.monitor import FileMonitor

# Create the API application and its shared folder monitor.
app = FastAPI(title="OneDrive Ingestion Folder Monitor")
monitor = FileMonitor()

@app.get("/", response_model=Dict[str, str])
def root() -> Dict[str, str]:
    """Return the application health status."""
    return {"message": "Fast API application is running. Status is healthy."}

@app.on_event("startup")
def start_monitor() -> None:
    """Start folder monitoring when the API application starts."""
    monitor.start()


@app.on_event("shutdown")
def stop_monitor() -> None:
    """Stop folder monitoring before the API application shuts down."""
    monitor.stop()


@app.get("/health")
def health() -> dict:
    """Return the monitor health status."""
    return monitor.health()


@app.get("/files")
def files() -> dict:
    """Return the configured folder and files detected by the monitor."""
    return monitor.status()
