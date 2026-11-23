"""Run the real CPU/PDF/FAISS integration test with DOCUMIND_TEST_REAL_MODEL=1."""
import os

import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models.knowledge import Chunk, FaissSnapshot
from app.rag.vector_store import VectorIndex

pytestmark = pytest.mark.skipif(
    os.environ.get("DOCUMIND_TEST_REAL_MODEL") != "1",
    reason="Set DOCUMIND_TEST_REAL_MODEL=1 to run local CPU inference.",
)


def test_real_pdf_search_and_restart(tmp_path):
    defaults = Settings()
    model_cache = defaults.model_cache_dir or defaults.storage_dir / "models"
    # The model is shared across opt-in runs while database and PDFs stay isolated.
    settings = Settings(data_dir=tmp_path, model_cache_dir=model_cache)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 80), "The observatory roof opens automatically when the sky is clear.")
        pdf.new_page().insert_text((50, 80), "Scholarship applications must be received by September 30.")
        content = pdf.tobytes()

    with TestClient(create_app(settings), base_url="http://localhost") as client:
        response = client.post("/api/documents/upload", files={"file": ("Program Guide.pdf", content, "application/pdf")})
        assert response.status_code == 201, response.text
        document = response.json()
        with client.app.state.engine.connect() as db:
            vectors = [np.frombuffer(value, dtype=np.float32) for value in db.scalars(select(Chunk.embedding))]
            assert len(vectors) == 2
            assert all(vector.shape == (384,) for vector in vectors)
            assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
            snapshot = db.scalar(select(FaissSnapshot.data))
            assert VectorIndex(snapshot).index.ntotal == 2
        payload = {"query": "When is the last day to apply for the scholarship?", "top_k": 1}
        search = client.post("/api/search", json=payload)
        assert search.status_code == 200, search.text
        hit, = search.json()
        assert hit["document_id"] == document["id"] and hit["page"] == 2
        assert hit["document_name"] == "Program Guide.pdf" and "September 30" in hit["text"]
        print(f"FAISS vectors: {len(vectors)} × {vectors[0].shape[0]}")
        print(f"Top hit: {hit['document_name']}, page {hit['page']}, score {hit['score']:.6f}, {hit['text']}")

    with TestClient(create_app(settings.model_copy(update={"offline": True})), base_url="http://localhost") as client:
        response = client.post("/api/search", json=payload)
        assert response.status_code == 200, response.text
        restarted, = response.json()
        assert restarted["chunk_id"] == hit["chunk_id"]
        assert restarted["page"] == hit["page"]
        assert restarted["score"] == pytest.approx(hit["score"], abs=1e-6)
        print("Offline restart returned the same chunk, page and similarity.")
