"""Embed review text and compare vectors for similarity search (RAG retrieval step)."""

import math

from app.models import Review
from app.recommend import get_llm_client
from app.settings import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns one list[float] vector per input text, same order."""
    if not texts:
        return []
    client = get_llm_client()
    response = client.embeddings.create(model=settings.llm_embedding_model, input=texts)
    return [item.embedding for item in response.data]


def embed_review(review: Review) -> None:
    """Compute and attach the embedding for a review's text (caller commits)."""
    review.embedding = embed_texts([review.text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """1.0 = identical direction, 0.0 = unrelated, -1.0 = opposite."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


def retrieve_relevant_reviews(
    reviews: list[Review], query_embedding: list[float], top_k: int
) -> list[Review]:
    """Rank reviews by similarity to query_embedding; return the top_k most relevant.

    Reviews without an embedding yet (not backfilled) are skipped, not retrievable.
    """
    scored = [
        (cosine_similarity(review.embedding, query_embedding), review)
        for review in reviews
        if review.embedding is not None
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [review for _, review in scored[:top_k]]
