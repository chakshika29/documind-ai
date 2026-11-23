"""Offline evaluation. Set DOCUMIND_TEST_RAG_EVAL=1 after caching both models."""
import json
import os
from pathlib import Path
from statistics import median
from time import perf_counter

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.rag.pipeline import normalize_fact

pytestmark = pytest.mark.skipif(
    os.getenv("DOCUMIND_TEST_RAG_EVAL") != "1", reason="Opt-in real CPU RAG evaluation"
)


def make_pdf(pages):
    with pymupdf.open() as pdf:
        for text in pages:
            pdf.new_page().insert_textbox((55, 55, 525, 220), text)
        return pdf.tobytes()


def test_rag_evaluation(tmp_path):
    dataset = json.loads((Path(__file__).parent / "fixtures" / "rag_evaluation.json").read_text(encoding="utf-8"))
    defaults = Settings()
    settings = Settings(data_dir=tmp_path, offline=True, llm_model=defaults.llm_model,
                        model_cache_dir=defaults.model_cache_dir or defaults.storage_dir / "models")
    k = 2
    recalls, latencies, cases = [], [], []
    correct_answers = correct_citations = total_citations = correct_abstentions = negative_cases = 0
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        document_ids = {}
        for name, pages in dataset["documents"].items():
            response = client.post("/api/documents/upload", files={"file": (name, make_pdf(pages), "application/pdf")})
            assert response.status_code == 201, response.text
            document_ids[name] = response.json()["id"]
        for case in dataset["cases"]:
            scope = [document_ids[name] for name in case.get("scope", document_ids)]
            expected = set(map(tuple, case["sources"]))
            retrieved = client.post("/api/search", json={"query": case["question"], "document_ids": scope,
                                                         "top_k": max(k, settings.search_top_k)})
            assert retrieved.status_code == 200, retrieved.text
            hits = retrieved.json()
            if expected:
                top = {(hit["document_name"], hit["page"]) for hit in hits[:k]}
                recalls.append(len(top & expected) / len(expected))
            began = perf_counter()
            response = client.post("/api/chat", json={"question": case["question"], "document_ids": scope})
            latencies.append(round((perf_counter() - began) * 1000))
            assert response.status_code == 200, response.text
            result = response.json()
            answer = normalize_fact(result["answer"]).strip(".!?")
            if expected:
                correct_answers += answer in {normalize_fact(item).strip(".!?") for item in case["answers"]}
            else:
                negative_cases += 1
                correct_abstentions += result["insufficient_evidence"] and not result["citations"]
            for citation in result["citations"]:
                total_citations += 1
                real_hit = any(all(hit[key] == citation[key] for key in ("chunk_id", "document_id", "page", "document_name"))
                               for hit in hits[:settings.search_top_k])
                assert real_hit, citation
                correct_citations += (citation["document_name"], citation["page"]) in expected
            cases.append({"question": case["question"], "answer": result["answer"],
                          "citations": [[item["document_name"], item["page"]] for item in result["citations"]],
                          "latency_ms": latencies[-1]})

    print(json.dumps({
        "recall_at_2": sum(recalls) / len(recalls), "factual_questions": len(recalls),
        "correct_answers": correct_answers, "correct_citations": correct_citations,
        "total_citations": total_citations, "correct_abstentions": correct_abstentions,
        "negative_cases": negative_cases, "median_latency_ms": median(latencies),
        "min_latency_ms": min(latencies), "max_latency_ms": max(latencies), "cases": cases,
    }, ensure_ascii=True))
