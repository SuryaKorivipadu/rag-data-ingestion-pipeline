from pathlib import Path

from read_service.app import reading


def test_process_next_document_chunks_txt_file(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "example.txt"
    source_path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    document = {
        "id": 7,
        "file_path": str(source_path),
        "file_name": source_path.name,
        "file_hash": "abc123",
    }
    statuses: list[tuple[int, str]] = []

    monkeypatch.setattr(reading, "_get_document", lambda file_id: document)
    monkeypatch.setattr(
        reading,
        "_update_document",
        lambda document_id, status, error_message=None: statuses.append(
            (document_id, status)
        ),
    )
    monkeypatch.setattr(reading, "READ_OUTPUT_DIR", tmp_path / "read")

    result = reading.process_next_document()

    assert result is not None
    assert result["document_id"] == 7
    assert result["status"] == "chunked"
    assert result["chunk_count"] >= 2
    assert statuses == [(7, "chunked")]
    assert Path(result["output_path"]).is_file()


def test_process_next_document_returns_none_when_no_new_file(monkeypatch) -> None:
    monkeypatch.setattr(reading, "_get_document", lambda file_id: None)

    assert reading.process_next_document() is None