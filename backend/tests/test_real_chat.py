"""Run with DOCUMIND_TEST_REAL_CHAT=1 after caching both models."""
import os

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.skipif(os.getenv("DOCUMIND_TEST_REAL_CHAT") != "1", reason="Opt-in real CPU generation")


def test_real_chat_offline_and_restart(tmp_path):
    defaults = Settings()
    settings = Settings(
        data_dir=tmp_path, offline=True, llm_model=defaults.llm_model,
        model_cache_dir=defaults.model_cache_dir or defaults.storage_dir / "models",
    )
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 80), "The observatory roof opens automatically on clear nights.")
        pdf.new_page().insert_text((50, 80), "The deadline for scholarship applications is September 30.")
        content = pdf.tobytes()
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        assert client.get("/api/ai/status").json()["status"] == "cached"
        upload = client.post("/api/documents/upload", files={"file": ("Scholarship Guide.pdf", content, "application/pdf")})
        assert upload.status_code == 201, upload.text
        response = client.post("/api/chat", json={
            "question": "What is the deadline for scholarship applications?",
            "document_ids": [upload.json()["id"]],
        })
        assert response.status_code == 200, response.text
        reply = response.json()
        assert "september 30" in reply["answer"].lower(), reply
        assert [(item["document_name"], item["page"]) for item in reply["citations"]] == [("Scholarship Guide.pdf", 2)]
        assert client.get("/api/ai/status").json()["ready"]
        print(f"Model answer: {reply['answer']} | Scholarship Guide.pdf p. 2 | {reply['elapsed_ms']} ms")

    with TestClient(create_app(settings), base_url="http://localhost") as client:
        detail = client.get(f"/api/conversations/{reply['conversation_id']}")
        assert detail.status_code == 200
        assert detail.json()["messages"][-1]["citations"] == reply["citations"]
        assert detail.json()["messages"][-1]["id"] == reply["message_id"]
        print("Conversation and its citations survived application restart.")
