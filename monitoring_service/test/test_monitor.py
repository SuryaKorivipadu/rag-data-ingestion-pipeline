from app.monitor import FileMonitor


def test_monitor_detects_files(tmp_path):
    file_path = tmp_path / "document.txt"
    file_path.write_text("content", encoding="utf-8")

    monitor = FileMonitor()
    monitor.folder = tmp_path
    monitor._scan()

    assert str(file_path) in monitor.status()["files"]


def test_monitor_health_and_missing_folder(tmp_path):
    monitor = FileMonitor()
    monitor.folder = tmp_path / "missing"

    assert monitor.health()["status"] == "healthy"
    assert monitor.status()["exists"] is False