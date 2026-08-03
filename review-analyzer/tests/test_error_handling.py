"""Verify unhandled exceptions log a traceback but never leak one to the client."""

import logging

from sqlalchemy.orm import Session

from app.models import Product, Review


def _seed_product(db: Session) -> int:
    product = Product(name="Test Widget", price=9.99, rating=4.0)
    db.add(product)
    db.flush()
    db.add(Review(product_id=product.id, text="Works great."))
    db.commit()
    return product.id


def test_unhandled_exception_returns_clean_500_and_logs_traceback(
    client, db, monkeypatch, caplog
):
    product_id = _seed_product(db)

    class FakeEmbeddings:
        def create(self, **kwargs):
            raise RuntimeError("boom - unexpected failure")

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr("app.recommend.OpenAI", lambda **kwargs: FakeClient())

    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/compare",
            json={"product_ids": [product_id], "requirement": "durable"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    # Never leak the traceback or exception details to the client.
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    assert "boom" not in response.text

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "expected an ERROR log line with the traceback"
    assert error_records[0].exc_info is not None

    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert error_records[0].request_id == request_id
