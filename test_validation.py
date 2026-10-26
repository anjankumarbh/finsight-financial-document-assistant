"""Checks for RAG retrieval, guardrails, and deterministic answer statuses."""

import pytest

from src import agent, rag
from src.rag import SearchIndex, chunk_text
from src.agent import _add_source_references, answer_question


@pytest.fixture(autouse=True)
def disable_external_gemini_for_unit_tests(monkeypatch):
    """Keep unit tests deterministic; the live Gemini path is used by the app."""
    # Tests verify local behavior and must never spend an API request.
    monkeypatch.setattr(agent, "api_key", lambda: "")
    monkeypatch.setattr(rag, "api_key", lambda: "")


def test_chunking_returns_nonempty_chunks():
    chunks = chunk_text("revenue " * 250, size=100, overlap=10)
    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)


def test_keyword_fallback_retrieves_matching_source(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document("Revenue grew from 100 to 120 lakh.", "statement.csv")
    hits = index.search("revenue grew")
    assert hits and hits[0].source == "statement.csv"


def test_unrelated_question_is_rejected_cleanly(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document("Revenue was 100 in FY2024.", "statement.csv")
    answer, hits, status = answer_question("Write a romantic poem", index)
    assert status == "out_of_scope"
    assert not hits
    assert "Please try asking about" in answer


def test_standalone_greeting_requires_documents_first(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    answer, hits, status = answer_question("Good morning", index)
    assert status == "documents_required"
    assert not hits
    assert "upload" in answer.lower()


def test_financial_question_requires_documents_first(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    answer, hits, status = answer_question("What happened to profits?", index)
    assert status == "documents_required"
    assert not hits
    assert "upload" in answer.lower()


def test_investment_decision_request_stays_out_of_scope(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document("Revenue was 100 in FY2024.", "statement.csv")
    answer, hits, status = answer_question("Should I buy this company's stock?", index)
    assert status == "out_of_scope"
    assert not hits
    assert "cannot recommend buying or selling" in answer


def test_management_risk_question_is_recognised_as_financial(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document("Operating cash flow fell from 8 to -2.", "statement.csv")
    answer, hits, status = answer_question(
        "What warning signs should management review?", index
    )
    assert status == "insufficient_data"
    assert not hits


def test_answer_includes_page_reference_when_present(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document(
        "Page 3\nRevenue increased from 100 to 120.", "annual_report.pdf"
    )
    answer, hits, status = answer_question("What changed in revenue?", index)
    assert status in {"gemini_not_configured", "agent_ok", "agent_error"}
    assert hits
    assert (
        "I found relevant information in the uploaded file: annual_report.pdf."
        in answer
    )


def test_source_note_is_not_added_twice_when_answer_already_names_file(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document("Revenue increased from 100 to 120.", "annual_report.pdf")
    hit = index.search("revenue")[0]
    answer = _add_source_references("The answer is in annual_report.pdf.", [hit])
    assert answer.count("annual_report.pdf") == 1


def test_plural_financial_question_retrieves_singular_field(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    index.add_document(
        "FY2024 net profit was 10 and FY2025 net profit was 9.", "statement.csv"
    )
    answer, hits, status = answer_question(
        "What happened to profits in these years?", index
    )
    assert status in {"gemini_not_configured", "agent_ok", "agent_error"}
    assert hits


def test_document_overview_includes_each_uploaded_source(tmp_path):
    index = SearchIndex(tmp_path / "vectors")
    for name in ("summary.pdf", "data.csv", "notes.txt", "data.xlsx"):
        index.add_document(f"Financial information from {name}.", name)
    _, hits, status = answer_question(
        "What have you read in the uploaded financial documents?", index
    )
    assert status in {"gemini_not_configured", "agent_ok", "agent_error"}
    assert {hit.source for hit in hits} == {
        "summary.pdf",
        "data.csv",
        "notes.txt",
        "data.xlsx",
    }
