"""Chunking, Gemini embeddings, Chroma retrieval, and a safe lexical fallback."""

from dataclasses import dataclass
import math
import re
from pathlib import Path

from .config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    RETRIEVAL_K,
    VECTOR_DIR,
    api_key,
)


# One result object keeps retrieved text, source, and ranking together.
@dataclass
class RetrievedChunk:
    """A text chunk returned by the vector or local search layer."""

    text: str
    source: str
    score: float


# Overlap helps a fact that crosses a chunk boundary remain searchable.
def chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping word windows for retrieval."""
    words = text.split()
    if not words:
        return []
    size = max(100, size)
    overlap = max(0, min(overlap, size - 1))
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
    return chunks


# The index hides the choice between Gemini/Chroma search and local fallback search.
class SearchIndex:
    """Store document chunks and retrieve the most relevant evidence."""

    def __init__(self, persist_directory: Path = VECTOR_DIR):
        """Prepare local records and the persistent Chroma folder."""
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._records: list[RetrievedChunk] = []
        self._store = None
        self._embedding_error = ""

    @property
    def ready_with_gemini(self) -> bool:
        """Tell the UI whether a Gemini-backed Chroma store is available."""
        return self._store is not None

    @property
    def embedding_error(self) -> str:
        """Return the latest embedding or semantic-search error, if any."""
        return self._embedding_error

    @property
    def has_documents(self) -> bool:
        """Tell the app whether at least one chunk has been indexed."""
        return bool(self._records) or self._store is not None

    def add_document(self, text: str, source: str) -> int:
        """Chunk one document and add it to Chroma when Gemini is configured."""
        chunks = chunk_text(text)
        for chunk in chunks:
            self._records.append(RetrievedChunk(chunk, source, 0.0))

        key = api_key()
        if key:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                from langchain_chroma import Chroma

                embeddings = GoogleGenerativeAIEmbeddings(
                    model=EMBEDDING_MODEL,
                    google_api_key=key,
                )
                self._store = Chroma(
                    collection_name="finsight_documents",
                    persist_directory=str(self.persist_directory),
                    embedding_function=embeddings,
                )
                metadata = [{"source": source} for _ in chunks]
                self._store.add_texts(chunks, metadatas=metadata)
            except Exception as exc:
                self._embedding_error = f"Gemini/Chroma indexing is unavailable: {exc}"
        return len(chunks)

    def search(self, question: str, k: int = RETRIEVAL_K) -> list[RetrievedChunk]:
        """Retrieve evidence with Chroma, then use local token search as fallback."""
        if self._store is not None:
            try:
                docs_scores = self._store.similarity_search_with_score(question, k=k)
                results = []
                for document, score in docs_scores:
                    source = document.metadata.get("source", "unknown")
                    results.append(
                        RetrievedChunk(document.page_content, source, float(score))
                    )
                return results
            except Exception as exc:
                self._embedding_error = (
                    f"Semantic search failed; using local keyword search: {exc}"
                )

        query = _normalised_tokens(question)
        ranked: list[RetrievedChunk] = []
        for record in self._records:
            words = _normalised_tokens(record.text)
            denominator = math.sqrt(max(1, len(query) * len(words)))
            overlap = len(query & words) / denominator
            ranked.append(RetrievedChunk(record.text, record.source, overlap))
        ranked = [item for item in ranked if item.score > 0]
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:k]

    def overview(self, chunks_per_source: int = 2) -> list[RetrievedChunk]:
        """Return a small amount of evidence from every uploaded source."""
        selected: list[RetrievedChunk] = []
        counts: dict[str, int] = {}
        for record in self._records:
            count = counts.get(record.source, 0)
            if count >= chunks_per_source:
                continue
            selected.append(record)
            counts[record.source] = count + 1
        return selected

    def clear(self) -> None:
        """Clear in-memory chunks and remove persisted Chroma files."""
        self._records.clear()
        self._store = None
        for path in self.persist_directory.iterdir():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil

                shutil.rmtree(path)


# Used only when embeddings are unavailable; this is not an AI model.
def _normalised_tokens(text: str) -> set[str]:
    """Create simple tokens for the no-API fallback search."""
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    plural_tokens = {
        token[:-1] for token in list(tokens) if len(token) > 3 and token.endswith("s")
    }
    tokens.update(plural_tokens)
    return tokens
