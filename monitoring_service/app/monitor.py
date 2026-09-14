import os
import threading
from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger(__name__)


class FileMonitor:
    """Poll an ingestion folder and log newly added or modified files."""

    def __init__(self) -> None:
        # Read the folder and polling interval once when the monitor is created.
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
        """Start the background watcher unless it is already running."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()
        logger.info("Monitoring folder: %s", self.folder)

    def stop(self) -> None:
        """Signal the watcher to stop and wait briefly for it to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def health(self) -> dict:
        """Return the basic health information used by the service."""
        return {"status": "healthy", "folder": str(self.folder)}

    def status(self) -> dict:
        """Return the folder state and the files seen in the latest scan."""
        return {
            "folder": str(self.folder),
            "exists": self.folder.is_dir(),
            "files": sorted(self._files),
        }

    def _watch(self) -> None:
        """Poll the configured folder until the stop event is set."""
        while not self._stop_event.is_set():
            if self.folder.is_dir():
                self._scan()
            else:
                logger.warning("Folder does not exist: %s", self.folder)
            self._stop_event.wait(self.interval)

    def _scan(self) -> None:
        """Compare the current file snapshot with the previous scan."""
        current_files = {
            str(path): path.stat().st_mtime
            for path in self.folder.iterdir()
            if path.is_file()
        }
        for path, modified_at in current_files.items():
            # A changed modification time indicates that an existing file was updated.
            if path not in self._files:
                logger.info("New file detected: %s", path)
            elif self._files[path] != modified_at:
                logger.info("File changed: %s", path)
        self._files = current_files