"""Verify /compare turns LLM provider failures into a clean 503, not a raw 500,
and that it grounds recommendations in retrieved reviews only."""
import json

import httpx
import openai
from sqlalchemy.orm import Session

from app.models import Product, Review
from app.settings import settings


def _seed_product(db: Session) -> int:
    product = Product(name="Test Widget", price=9.99, rating=4.0)
    db.add(product)
    db.flush()
    db.add(Review(product_id=product.id, text="Works great."))
    db.commit()
    return product.id


def test_provider_failure_returns_structured_503(client, db, monkeypatch):
    """When the LLM provider is unreachable, /compare returns 503 with a
    clean JSON message, and never leaks the underlying stack trace."""
    product_id = _seed_product(db)

    class FakeEmbeddings:
        def create(self, **kwargs):
            raise openai.APIConnectionError(
                request=httpx.Request("POST", "http://fake-llm/v1/embeddings")
            )

    class FakeCompletions:
        def create(self, **kwargs):
            raise openai.APIConnectionError(
                request=httpx.Request("POST", "http://fake-llm/v1/chat/completions")
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()
        embeddings = FakeEmbeddings()

    monkeypatch.setattr("app.recommend.OpenAI", lambda **kwargs: FakeClient())

    response = client.post(
        "/compare",
        json={"product_ids": [product_id], "requirement": "durable and cheap"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body == {
        "detail": "Recommendation service is temporarily unavailable. Please try again shortly."
    }
    # No traceback / exception internals leaked to the client.
    assert "Traceback" not in response.text
    assert "APIConnectionError" not in response.text


def test_compare_sends_only_retrieved_reviews_to_the_llm(client, db, monkeypatch):
    """/compare embeds the requirement, retrieves the top-k most similar reviews per
    product, and sends only those to the LLM — not the product's full review list."""
    monkeypatch.setattr(settings, "retrieval_top_k", 1)

    product = Product(name="Test Widget", price=9.99, rating=4.0)
    db.add(product)
    db.flush()
    close = Review(
        product_id=product.id, text="Great grip in mud", embedding=[1.0, 0.0]
    )
    far = Review(
        product_id=product.id,
        text="Battery life is disappointing",
        embedding=[0.0, 1.0],
    )
    db.add_all([close, far])
    db.commit()

    captured = {}

    class FakeEmbeddings:
        def create(self, **kwargs):
            class Item:
                embedding = [1.0, 0.0]

            class Response:
                data = [Item()]

            return Response()

    class FakeMessage:
        content = json.dumps(
            {
                "recommended_product": "Test Widget",
                "reason": "Good grip",
                "main_positive": "Grip",
                "main_complaint": "none",
                "confidence": 0.9,
            }
        )

    class FakeCompletions:
        def create(self, **kwargs):
            captured["user_prompt"] = kwargs["messages"][1]["content"]

            class Choice:
                message = FakeMessage()

            class Response:
                choices = [Choice()]
                usage = None

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()
        embeddings = FakeEmbeddings()

    monkeypatch.setattr("app.recommend.OpenAI", lambda **kwargs: FakeClient())

    response = client.post(
        "/compare",
        json={"product_ids": [product.id], "requirement": "great grip"},
    )

    assert response.status_code == 200
    user_prompt = captured["user_prompt"]
    assert "Great grip in mud" in user_prompt
    assert "Battery life is disappointing" not in user_prompt
