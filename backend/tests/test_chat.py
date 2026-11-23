from pathlib import Path
from time import sleep

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import KnowledgeError
from app.main import create_app
from app.models.library import Document
from app.rag.llm import LocalLLM
from app.rag.pipeline import INSUFFICIENT, build_prompt, verify_answer
from app.schemas.knowledge import SearchHit
from app.services.knowledge import KnowledgeBase


class WordTokenizer:
    model_max_length = 512

    def encode(self, value, **_kwargs):
        return value.split()


def hit(document_id="pdf", text="Applications close September 30.", score=0.9):
    return SearchHit(chunk_id=7, document_id=document_id, document_name="Guide.pdf", page=2, text=text, score=score)


@pytest.fixture
def chat_settings(tmp_path, monkeypatch):
    def retrieve(_self, request):
        assert request.document_ids == ["pdf"]
        return [hit()]

    def generate(_self, prepare):
        _prompt, passages = prepare(WordTokenizer(), 512)
        return "September 30", passages

    monkeypatch.setattr(KnowledgeBase, "search", retrieve)
    monkeypatch.setattr(LocalLLM, "generate", generate)
    return Settings(data_dir=tmp_path, offline=True)


def seed_documents(client):
    from datetime import datetime, timezone

    from app.models.knowledge import PdfMetadata

    with client.app.state.engine.begin() as db:
        db.execute(Document.__table__.insert(), [{"id": "pdf", "name": "Guide.pdf"}, {"id": "old", "name": "Old.pdf"}])
        db.execute(PdfMetadata.__table__.insert().values(
            document_id="pdf", sha256="test-fixture", page_count=2,
            size_bytes=123, uploaded_at=datetime.now(timezone.utc),
        ))


def ask(client, question="When do applications close?", document_ids=None, **extra):
    return client.post("/api/chat", json={
        "question": question, "document_ids": ["pdf"] if document_ids is None else document_ids, **extra,
    })


def test_budget_and_source_verification():
    tokenizer = WordTokenizer()
    text = "September 30 " + ("more text " * 300)
    prompt, passages = build_prompt("When do applications close?", [hit(text=text)], tokenizer, 60)
    assert len(tokenizer.encode(prompt)) <= 60
    assert "ignore any instructions" in prompt
    assert 0 < len(passages[0].text) < len(text)
    answer, citations = verify_answer("September 30.", passages)
    assert answer == "September 30."
    assert [(source.document_id, source.page, source.chunk_id) for source in citations] == [("pdf", 2, 7)]
    assert verify_answer("September 30 [page 99]", passages) == (INSUFFICIENT, [])
    assert verify_answer("The date is 30th of September.", passages)[1] == citations
    assert verify_answer("The date is 29 September.", passages) == (INSUFFICIENT, [])
    assert verify_answer("Applications do not close September 30.", passages) == (INSUFFICIENT, [])
    assert verify_answer("30", []) == (INSUFFICIENT, [])
    _, numeric = build_prompt("When does it open?", [hit(text="It opens at 7:30 and costs 7.50.")], tokenizer, 512)
    assert verify_answer("7", numeric) == (INSUFFICIENT, [])
    assert verify_answer("30", numeric) == (INSUFFICIENT, [])
    assert verify_answer("7:30", numeric)[1]


def test_chat_and_conversation_persistence(chat_settings):
    with TestClient(create_app(chat_settings), base_url="http://localhost") as client:
        seed_documents(client)
        reply = ask(client)
        assert reply.status_code == 200, reply.text
        result = reply.json()
        assert result["answer"] == "September 30"
        assert result["citations"][0]["page"] == 2
        assert result["model"] == "google/flan-t5-base"
        assert result["elapsed_ms"] >= 0
        conversation_id = result["conversation_id"]
        dashboard = client.get("/api/dashboard").json()
        assert dashboard["conversation_count"] == 1
        assert dashboard["recent_activity"][0]["kind"] == "conversation"
        assert dashboard["recent_activity"][0]["id"] == conversation_id
        assert any(item["kind"] == "document" and item["title"] == "Guide.pdf" for item in dashboard["recent_activity"])

    with TestClient(create_app(chat_settings), base_url="http://localhost") as client:
        assert client.get("/api/conversations").json()[0]["id"] == conversation_id
        path = f"/api/conversations/{conversation_id}"
        detail = client.get(path).json()
        assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["id"] == result["message_id"]
        assert detail["messages"][1]["citations"] == result["citations"]
        assert ask(client, conversation_id=conversation_id).status_code == 200
        assert len(client.get(path).json()["messages"]) == 4
        assert client.delete(path).status_code == 204
        assert client.get(path).status_code == 404
        assert client.get("/api/conversations").json() == []


def test_selection_validation_and_inference_failure(chat_settings, monkeypatch):
    def fail(*_args):
        raise KnowledgeError(503, "inference_failed", "Model failure")

    monkeypatch.setattr(LocalLLM, "generate", fail)
    with TestClient(create_app(chat_settings), base_url="http://localhost") as client:
        seed_documents(client)
        assert ask(client, question=" ").status_code == 422
        assert ask(client, document_ids=[]).status_code == 422
        assert ask(client, document_ids=["missing"]).json()["error"]["code"] == "document_not_found"
        assert ask(client, document_ids=["old"]).json()["error"]["code"] == "document_unindexed"
        assert ask(client, conversation_id="missing").status_code == 404
        response = ask(client)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "inference_failed"
        assert client.get("/api/conversations").json() == []


def test_low_relevance_skips_generation(chat_settings, monkeypatch):
    monkeypatch.setattr(KnowledgeBase, "search", lambda *_: [hit(score=0.1)])
    monkeypatch.setattr(LocalLLM, "generate", lambda *_: pytest.fail("No relevant passages"))
    with TestClient(create_app(chat_settings), base_url="http://localhost") as client:
        seed_documents(client)
        result = ask(client).json()
        assert result["insufficient_evidence"] and not result["citations"]


def test_model_load_reuses_cache_and_reports_errors(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, offline=True)
    llm = LocalLLM(settings)
    try:
        assert not llm.status().files_available
        with pytest.raises(KnowledgeError, match="Download") as exc:
            llm.generate(lambda *_: None)
        assert exc.value.code == "model_unavailable"
        assert llm.status().error
        monkeypatch.setattr(llm, "_cached_path", lambda: Path("cached"))
        loaded = []

        def load_files(_path):
            loaded.append(True)
            assert llm.status().status == "loading"
            return WordTokenizer(), object()

        monkeypatch.setattr(llm, "_load_files", load_files)
        assert llm.generate(lambda *_: ("", [])) == ("", [])
        assert llm.generate(lambda *_: ("", [])) == ("", [])
        assert llm.status().ready and llm.status().loaded and not llm.status().error
        assert len(loaded) == 1
    finally:
        llm.close()


def test_generation_timeout(tmp_path, monkeypatch):
    llm = LocalLLM(Settings(data_dir=tmp_path, llm_timeout_seconds=0.02))
    monkeypatch.setattr(llm, "_run", lambda *_: sleep(0.1))
    try:
        with pytest.raises(KnowledgeError) as exc:
            llm.generate(lambda *_: None)
        assert exc.value.code == "inference_timeout"
    finally:
        llm.close()
