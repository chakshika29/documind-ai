from hashlib import blake2b

import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import KnowledgeError
from app.main import create_app
from app.rag.embeddings import DIMENSIONS, Embeddings
from app.rag.vector_store import VectorIndex
from app.services.chunking import chunk_pages
from app.services.pdf import PageText, extract_pages


def make_pdf(*texts: str) -> bytes:
    with pymupdf.open() as pdf:
        for text in texts:
            page = pdf.new_page()
            if text:
                page.insert_text((60, 70), text)
        return pdf.tobytes()


def upload(client, content, name="Guide.pdf"):
    return client.post("/api/documents/upload", files={"file": (name, content, "application/pdf")})


@pytest.fixture
def settings(tmp_path, monkeypatch):
    def encode(_self, texts):
        vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
        for row, text in zip(vectors, texts, strict=True):
            for word in text.lower().split():
                key = int.from_bytes(blake2b(word.encode(), digest_size=2).digest())
                row[key % DIMENSIONS] += 1
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    monkeypatch.setattr(Embeddings, "encode", encode)
    return Settings(data_dir=tmp_path, max_upload_mb=1, offline=True)


@pytest.mark.parametrize(
    ("content", "code"),
    [(b"this is not a PDF", "invalid_pdf_signature"), (b"%PDF-1.7\ntruncated", "corrupt_pdf")],
)
def test_pdf_signature_and_corruption(content, code):
    with pytest.raises(KnowledgeError) as exc:
        extract_pages(content, 10)
    assert exc.value.code == code


def test_extract_preserves_pages_and_rejects_no_text():
    pages = extract_pages(make_pdf("First page", "", "Third page"), 10)
    assert [(page.number, page.text.strip()) for page in pages] == [
        (1, "First page"), (2, ""), (3, "Third page")
    ]
    with pytest.raises(KnowledgeError) as exc:
        extract_pages(make_pdf(""), 10)
    assert exc.value.code == "no_pdf_text"


def test_chunking_long_paragraph_overlap_and_source_text():
    source = "abcdefghijklmnopqrstuvwxyz" * 6
    chunks = chunk_pages("doc", [PageText(2, source), PageText(3, "original\n  passage"), PageText(4, " ")], 40, 8)
    assert all(chunk.document_id == "doc" and 0 < len(chunk.text) <= 40 for chunk in chunks)
    assert chunks[0].text[-8:] == chunks[1].text[:8]
    reconstructed = chunks[0].text + "".join(chunk.text[8:] for chunk in chunks[1:-1])
    assert reconstructed == source
    assert chunks[-1].page == 3
    assert chunks[-1].text == "original\n  passage"
    assert chunks[-1].normalized_text == "original passage"


def test_faiss_empty_snapshot_and_removal():
    vector = np.zeros((1, DIMENSIONS), dtype=np.float32)
    vector[0, 0] = 1
    index = VectorIndex()
    assert index.search(vector, 2) == []
    index.add([32], vector)
    reloaded = VectorIndex(index.serialize())
    assert reloaded.search(vector, 2) == [(32, 1.0)]
    reloaded.remove([32])
    assert reloaded.search(vector, 2) == []


def test_api_ingestion_search_restart_filter_and_delete(settings):
    document = make_pdf("piano orchestra violin", "submarine sonar ocean")
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        assert client.get("/api/documents").json() == []
        assert client.post("/api/search", json={"query": "ocean"}).json() == []
        first = upload(client, document, "../../Field Guide.pdf")
        assert first.status_code == 201, first.text
        first = first.json()
        assert first["name"] == "Field Guide.pdf"
        assert (first["page_count"], first["status"]) == (2, "indexed")
        second = upload(client, make_pdf("desert sand dunes"), "Desert.pdf").json()
        assert upload(client, document, "Copy.pdf").status_code == 409
        assert len(list((settings.storage_dir / "uploads").glob("*.pdf"))) == 2
        assert client.get("/api/dashboard").json()["document_count"] == 2
        assert client.get(f"/api/documents/{first['id']}").json() == first

    with TestClient(create_app(settings), base_url="http://localhost") as client:
        response = client.post("/api/search", json={"query": "submarine sonar", "top_k": 1})
        assert response.status_code == 200, response.text
        hit, = response.json()
        assert hit["document_id"] == first["id"]
        assert hit["document_name"] == "Field Guide.pdf"
        assert hit["page"] == 2 and hit["score"] > 0.8
        restricted, = client.post("/api/search", json={
            "query": "submarine sonar", "document_ids": [second["id"]],
        }).json()
        assert restricted["document_id"] == second["id"]
        assert client.post("/api/search", json={"query": "sonar", "document_ids": []}).json() == []
        assert client.delete(f"/api/documents/{first['id']}").status_code == 204
        assert client.get(f"/api/documents/{first['id']}").status_code == 404
        assert not (settings.storage_dir / "uploads" / f"{first['id']}.pdf").exists()
        assert client.get("/api/dashboard").json()["document_count"] == 1
        assert [hit["document_id"] for hit in client.post("/api/search", json={"query": "sonar"}).json()] == [second["id"]]
        assert upload(client, document).status_code == 201


def test_api_validation_and_failures(settings, monkeypatch):
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        assert client.post("/api/documents/upload").status_code == 422
        assert upload(client, b"x" * (1024 * 1024 + 1)).status_code == 413
        assert upload(client, b"fake PDF").json()["error"]["code"] == "invalid_pdf_signature"
        assert upload(client, make_pdf("")).json()["error"]["code"] == "no_pdf_text"
        for payload in ({"query": " "}, {"query": "x", "top_k": 31}, {"query": "x", "document_ids": [""]}):
            assert client.post("/api/search", json=payload).status_code == 422

        def fail(_self):
            raise RuntimeError("Simulated FAISS write failure")

        monkeypatch.setattr(VectorIndex, "serialize", fail)
        response = upload(client, make_pdf("A valid text PDF"))
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "index_unavailable"
        assert client.get("/api/documents").json() == []
        assert not list((settings.storage_dir / "uploads").glob("*.pdf"))
