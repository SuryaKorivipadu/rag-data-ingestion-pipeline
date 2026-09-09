import os
import threading
from pathlib import Path

from app.utils.logging import get_logger


logger = get_logger(__name__)


class FileMonitor:
    def __init__(self) -> None:
        configured_path = os.getenv(
            "ONEDRIVE_INGESTION_FOLDER",
            "~/OneDrive/ingestion_folder",
        )
        self.folder = Path(configured_path).expanduser()
        self.interval = float(os.getenv("MONITOR_INTERVAL_SECONDS", "5"))
        self._files: dict[str, float] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()
        logger.info("Monitoring folder: %s", self.folder)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def health(self) -> dict:
        return {"status": "healthy", "folder": str(self.folder)}

    def status(self) -> dict:
        return {
            "folder": str(self.folder),
            "exists": self.folder.is_dir(),
            "files": sorted(self._files),
        }

    def _watch(self) -> None:
        while not self._stop_event.is_set():
            if self.folder.is_dir():
                self._scan()
            else:
                logger.warning("Folder does not exist: %s", self.folder)
            self._stop_event.wait(self.interval)

    def _scan(self) -> None:
        current_files = {
            str(path): path.stat().st_mtime
            for path in self.folder.iterdir()
            if path.is_file()
        }
        for path, modified_at in current_files.items():
            if path not in self._files:
                logger.info("New file detected: %s", path)
            elif self._files[path] != modified_at:
                logger.info("File changed: %s", path)
        self._files = current_files