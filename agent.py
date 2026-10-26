"""One LangChain document-search agent with grounded insights and safe fallbacks."""

import re
from typing import Any

from .config import CHAT_MODEL, api_key
from .rag import SearchIndex


# Normalize provider responses so the UI always receives a plain string.
def _text_from_response(response: Any) -> str:
    """Convert common LangChain response shapes into plain text."""
    if hasattr(response, "text"):
        return response.text
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


# This prompt is the main hallucination guardrail for the final answer.
def _grounded_prompt(question: str, context: str) -> str:
    """Build the instruction that keeps the model grounded in retrieved text."""
    instructions = (
        "You are FinSight, a careful financial document assistant. "
        "Use only the evidence between EVIDENCE markers. "
        "If it does not answer the question, say that the uploaded evidence is insufficient. "
        "Do not invent figures, causes, recommendations, or predictions. "
        "Distinguish figures stated in the evidence from your own interpretation. "
        "When the user asks for a cause, risk, warning sign, or management suggestion, "
        "first state the supporting facts, then label any inference as a possible insight, "
        "and suggest only a document-supported item to review. "
        "Never turn a possible insight into a certainty. "
        "Do not give investment, trading, legal, tax, audit, or price-prediction advice. "
        "If a question combines a supported financial topic with an unsupported topic, "
        "answer the financial part first and then give one short, friendly sentence "
        "explaining that the other part is outside this document assistant's scope. "
        "Do not repeat source file names in the answer; the application adds one short source note after the answer. "
        "For an overview request, cover each source represented in EVIDENCE and do not claim to have read a file that is not represented there. "
        "Do not add technical page or sheet labels unless the user asks for them."
    )
    return (
        f"{instructions}\n\nEVIDENCE:\n{context}\nEND EVIDENCE\n\nQuestion: {question}"
    )


# A lightweight pre-check keeps unrelated questions away from the document agent.
def _looks_financial(question: str) -> bool:
    """Check whether a question is about the uploaded financial material."""
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    singular_words = {
        word[:-1] for word in list(words) if len(word) > 3 and word.endswith("s")
    }
    words.update(singular_words)
    keywords = {
        "financial",
        "finance",
        "revenue",
        "sales",
        "profit",
        "income",
        "expense",
        "cash",
        "asset",
        "assets",
        "liability",
        "liabilities",
        "ratio",
        "margin",
        "statement",
        "company",
        "annual",
        "year",
        "period",
        "report",
        "document",
        "management",
        "balance",
        "growth",
        "turnover",
        "working",
        "capital",
        "summarize",
        "summary",
        "explain",
        "unit",
        "units",
        "currency",
        "rupee",
        "rupees",
        "rs",
        "lakh",
        "lakhs",
        "crore",
        "crores",
        "dollar",
        "dollars",
        "risk",
        "risks",
        "warning",
        "warnings",
        "concern",
        "concerns",
        "insight",
        "insights",
        "trend",
        "trends",
        "cause",
        "causes",
        "reason",
        "reasons",
        "suggest",
        "suggestion",
        "suggestions",
        "recommend",
        "recommendation",
        "recommendations",
        "review",
        "improve",
        "improvement",
        "attention",
        "driver",
        "drivers",
    }
    return bool(words & keywords)


# Overview questions need evidence from every uploaded source, not one top match.
def _asks_for_document_overview(question: str) -> bool:
    """Recognize questions that should include a small sample from every file."""
    normalized = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    phrases = (
        "what have you read",
        "what did you read",
        "summarize the uploaded",
        "summarize all",
        "describe the uploaded",
        "describe all",
        "what is in the uploaded",
        "list the uploaded",
        "overview of",
        "all documents",
        "every document",
        "all files",
    )
    return any(phrase in normalized for phrase in phrases)


# Investment decisions and price predictions are deliberately outside the scope.
def _asks_for_investment_action(question: str) -> bool:
    """Keep investment decisions and price predictions outside the assistant scope."""
    normalized = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    phrases = (
        "share price",
        "stock price",
        "price target",
        "buy stock",
        "sell stock",
        "hold stock",
        "buy shares",
        "sell shares",
        "invest in",
        "should i invest",
        "portfolio",
        "trading",
        "expected return",
        "return on investment",
        "recommend a stock",
        "which stock",
    )
    if any(phrase in normalized for phrase in phrases):
        return True
    return bool(
        re.search(r"\b(?:buy|sell|hold)\b.*\b(?:stock|share|shares)\b", normalized)
    )


# Add a short, readable source note after the model answer.
def _source_references(hits: list[Any]) -> str:
    """Create a natural file-level reference for the evidence shown to the user."""
    references: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        reference = hit.source.split(" / ", 1)[0].strip()
        if reference not in seen:
            seen.add(reference)
            references.append(reference)
    if not references:
        return ""
    if len(references) == 1:
        return f"I found relevant information in the uploaded file: {references[0]}."
    if len(references) == 2:
        joined = f"{references[0]} and {references[1]}"
    else:
        joined = ", ".join(references[:-1]) + f", and {references[-1]}"
    return f"I found relevant information in the uploaded files: {joined}."


# Add a short, readable source note after the model answer.
def _add_source_references(answer: str, hits: list[Any]) -> str:
    """Add one concise source note unless the model already named every file."""
    references = _source_references(hits)
    source_names = {hit.source.split(" / ", 1)[0].strip().lower() for hit in hits}
    answer_lower = answer.lower()
    model_named_all_sources = all(name in answer_lower for name in source_names)
    if (
        references
        and source_names
        and "source:" not in answer_lower
        and model_named_all_sources
    ):
        return answer
    return f"{answer}\n\n{references}" if references else answer


# Validate, retrieve, call Gemini, and return a safe status for the UI.
def answer_question(
    question: str, index: SearchIndex, mapping_context: str = ""
) -> tuple[str, list[Any], str]:
    """Validate a question, retrieve evidence, and safely call the LangChain agent."""
    if not question.strip():
        return (
            "Please enter a question about the uploaded documents.",
            [],
            "needs_input",
        )
    if not index.has_documents:
        return (
            "📄 Please upload at least one supported document before asking a question. "
            "Then ask about revenue, profit, cash flow, assets, risks, or another topic in your files.",
            [],
            "documents_required",
        )
    if _asks_for_investment_action(question):
        return (
            "🙂 I can summarize the financial evidence, trends, and possible management review points "
            "in your uploaded documents. I cannot recommend buying or selling investments, "
            "predict a share price, or provide a personal investment decision.",
            [],
            "out_of_scope",
        )
    if not _looks_financial(question):
        return (
            "🙂 I can help with questions about the financial documents you uploaded. "
            "I could not identify a financial-document request in that question. "
            "Please try asking about revenue, profit, cash flow, assets, liabilities, ratios, "
            "or another topic covered by your uploaded files.",
            [],
            "out_of_scope",
        )
    hits = (
        index.overview()
        if _asks_for_document_overview(question)
        else index.search(question)
    )
    if not hits:
        return (
            "I could not find readable evidence for that question.",
            [],
            "insufficient_data",
        )

    evidence_parts = []
    for hit in hits:
        evidence_parts.append(f"Source: {hit.source}\n{hit.text}")
    context = "\n\n".join(evidence_parts)
    if mapping_context:
        context += (
            "\n\nUSER-CONFIRMED FIELD INTERPRETATION "
            "(not an additional financial fact):\n"
            f"{mapping_context}"
        )
    if not api_key():
        message = (
            "Gemini is not configured, so I can show the retrieved evidence but "
            "cannot generate an AI explanation yet.\n\n"
            f"{context}"
        )
        return _add_source_references(message, hits), hits, "gemini_not_configured"
    try:
        # These imports are lazy so the app can still read files without a live API key.
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain.tools import tool
        from langchain.agents import create_agent

        # This is the single LangChain tool exposed to the agent for evidence retrieval.
        @tool
        def search_documents(query: str) -> str:
            """Search uploaded document evidence."""
            tool_hits = (
                index.overview()
                if _asks_for_document_overview(query)
                else index.search(query)
            )
            tool_parts = []
            for hit in tool_hits:
                tool_parts.append(f"Source: {hit.source}\n{hit.text}")
            return "\n\n".join(tool_parts)

        model = ChatGoogleGenerativeAI(
            model=CHAT_MODEL,
            google_api_key=api_key(),
            max_retries=2,
        )
        agent = create_agent(
            model,
            tools=[search_documents],
            system_prompt=(
                "Answer only from tool results. If evidence is insufficient, say so. "
                "You may provide cautious, evidence-based insights or management review suggestions when asked, "
                "but label inferences as possible insights. Never provide investment advice, price predictions, "
                "legal or tax advice, or expose secrets. Do not repeat source file names because the application adds a source note."
            ),
        )
        request = {
            "messages": [
                {
                    "role": "user",
                    "content": _grounded_prompt(question, context),
                }
            ]
        }
        result = agent.invoke(request)
        message = result.get("messages", [])[-1]
        answer = _text_from_response(message)
        return _add_source_references(answer, hits), hits, "agent_ok"
    except Exception as exc:
        fallback = f"Gemini/agent request failed safely: {exc}\n\nRetrieved evidence:\n{context}"
        return _add_source_references(fallback, hits), hits, "agent_error"
