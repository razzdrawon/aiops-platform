"""
Chunk, embed, and upsert internal runbooks into Pinecone so the Diagnoser can do RAG at runtime.
Kept synchronous because Pinecone and LangChain vector store clients are blocking-first here.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

logger = logging.getLogger("knowledge.indexer")

RUNBOOK_DIR = Path(__file__).resolve().parent / "runbooks"
EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "aiops-runbooks")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
# text-embedding-3-small defaults to 1536 dims
EMBED_DIM = int(os.getenv("OPENAI_EMBEDDING_DIM", "1536"))
MATCH_DISTANCE_MAX = float(os.getenv("RAG_MATCH_DISTANCE_MAX", "0.45"))


def _chunk_markdown(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else len(text)
    return [c for c in chunks if c]


def load_runbook_documents() -> list[Document]:
    docs: list[Document] = []
    for path in sorted(RUNBOOK_DIR.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        for i, chunk in enumerate(_chunk_markdown(body)):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": path.name, "chunk": i},
                )
            )
    return docs


def _index_names(pc: Pinecone) -> set[str]:
    resp = pc.list_indexes()
    items = getattr(resp, "indexes", None) or resp or []
    names: set[str] = set()
    for item in items:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            names.add(str(item.get("name", "")))
        else:
            n = getattr(item, "name", None)
            if n:
                names.add(str(n))
    return {n for n in names if n}


def ensure_index(pc: Pinecone) -> None:
    if INDEX_NAME in _index_names(pc):
        return
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBED_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
    )


def build_vector_store() -> PineconeVectorStore:
    api_key = os.environ["PINECONE_API_KEY"]
    pc = Pinecone(api_key=api_key)
    ensure_index(pc)
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    return PineconeVectorStore.from_existing_index(
        embedding=embeddings,
        index_name=INDEX_NAME,
    )


def index_runbooks() -> int:
    docs = load_runbook_documents()
    if not docs:
        raise RuntimeError(f"No runbooks found under {RUNBOOK_DIR}")

    api_key = os.environ["PINECONE_API_KEY"]
    _ = os.environ["OPENAI_API_KEY"]

    pc = Pinecone(api_key=api_key)
    ensure_index(pc)
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)

    PineconeVectorStore.from_documents(
        documents=docs,
        embedding=embeddings,
        index_name=INDEX_NAME,
    )
    return len(docs)


async def search_runbooks(query: str, k: int = 4) -> tuple[list[Document], bool]:
    """
    Returns (documents, matched_high_confidence).
    matched_high_confidence is False when nothing retrieved or best match is too weak — graph branches on this.
    """
    if not os.getenv("PINECONE_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        return [], False

    def _search() -> tuple[list[Document], bool]:
        try:
            vs = build_vector_store()
            pairs = vs.similarity_search_with_score(query, k=k)
        except Exception:
            logger.exception("Pinecone retrieval failed — treating as no match")
            return [], False
        if not pairs:
            return [], False
        docs_only = [d for d, _ in pairs]
        best = pairs[0][1]
        # cosine distance: lower is closer; treat above threshold as "no confident match"
        matched = best <= MATCH_DISTANCE_MAX
        return docs_only, matched

    return await asyncio.to_thread(_search)


def main() -> None:
    count = index_runbooks()
    print(f"Indexed {count} chunks into Pinecone index '{INDEX_NAME}'.")


if __name__ == "__main__":
    main()
