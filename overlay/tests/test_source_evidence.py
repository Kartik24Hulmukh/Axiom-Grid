"""Real extraction/ask source links must resolve to actual retained evidence."""
from fastapi.testclient import TestClient

from overlay import server


def test_unknown_document_does_not_invent_a_rendered_source():
    with TestClient(server.app) as client:
        response = client.get("/api/source/nonexistent")
    assert response.status_code == 404
    assert "kairo://" not in response.text


def test_extracted_fields_have_working_source_evidence():
    with TestClient(server.app) as client:
        response = client.post("/api/extract-document", json={"file": "sample_memo_01.txt"})
        assert response.status_code == 200
        fields = response.json()["fields"]
        assert fields
        for field in fields.values():
            source = client.get(field["source_link"])
            assert source.status_code == 200
            assert source.json()["source_text"]
            assert source.json()["regions"]
            assert source.json()["render_url"] is None


def test_invalid_source_coordinates_are_not_echoed():
    with TestClient(server.app) as client:
        assert client.get("/api/source/nonexistent?x=nan").status_code == 422
        assert client.get("/api/source/nonexistent?page=0").status_code == 422