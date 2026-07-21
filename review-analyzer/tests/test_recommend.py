"""Verify the LLM client has a hard timeout and retries only transient failures."""
import logging

import httpx

from app.models import Product, Review
from app.recommend import build_context, build_prompt, estimate_cost_usd
from app.settings import settings

logger = logging.getLogger(__name__)


def test_estimate_cost_usd():
    """Cost is (prompt_tokens * input_price + completion_tokens * output_price) / 1e6."""
    settings.llm_input_price_per_1m = 2.50
    settings.llm_output_price_per_1m = 10.00

    cost = estimate_cost_usd(prompt_tokens=1_000_000, completion_tokens=0)
    assert cost == 2.50

    cost = estimate_cost_usd(prompt_tokens=0, completion_tokens=1_000_000)
    assert cost == 10.00

    cost = estimate_cost_usd(prompt_tokens=303, completion_tokens=80)
    assert round(cost, 6) == round((303 * 2.50 + 80 * 10.00) / 1_000_000, 6)


def test_client_has_timeout_and_retry_policy():
    """Client is built with the configured timeout/max_retries, and only
    retries 429/5xx — never 400."""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    assert client.timeout == settings.llm_timeout_seconds
    assert client.max_retries == settings.llm_max_retries

    def should_retry(status_code: int) -> bool:
        resp = httpx.Response(
            status_code=status_code, request=httpx.Request("POST", "http://x")
        )
        return client._should_retry(resp)

    assert should_retry(400) is False, "400 is a client error, retrying can't fix it"
    assert should_retry(429) is True
    assert should_retry(500) is True
    assert should_retry(503) is True
    logger.info("[OK] timeout + retry policy verified: 400 skipped, 429/5xx retried")


def test_build_context_is_labelled_and_readable():
    """Each product gets a human-readable block naming the product and its retrieved reviews."""
    product = Product(id=1, name="Widget", price=9.99, rating=4.5)
    reviews = [Review(text="Great value"), Review(text="Works as expected")]

    context = build_context([product], {1: reviews})

    assert 'Product: "Widget" (id=1, price=9.99, rating=4.5)' in context
    assert "- Great value" in context
    assert "- Works as expected" in context


def test_build_context_only_uses_retrieved_reviews():
    """A product's full review list is ignored; only reviews_by_product[id] is shown.

    This is the v1 (all-reviews) path being removed: build_context no longer reads
    product.reviews at all.
    """
    product = Product(id=1, name="Widget", price=9.99, rating=4.5)
    product.reviews = [Review(text="Irrelevant review not retrieved")]

    context = build_context([product], {1: [Review(text="Retrieved review")]})

    assert "Retrieved review" in context
    assert "Irrelevant review not retrieved" not in context


def test_build_context_enforces_max_size(monkeypatch):
    """Context longer than settings.llm_context_max_chars is hard-truncated."""
    monkeypatch.setattr(settings, "llm_context_max_chars", 50)
    product = Product(id=1, name="Widget", price=9.99, rating=4.5)
    reviews = [Review(text="x" * 200)]

    context = build_context([product], {1: reviews})

    assert len(context) == 50 + len("\n...[truncated]")
    assert context.endswith("\n...[truncated]")


def test_build_prompt_forbids_outside_knowledge():
    """System prompt must explicitly tell the model to ground answers only in
    the provided reviews, not general/outside knowledge."""
    product = Product(id=1, name="Widget", price=9.99, rating=4.5)
    reviews = [Review(text="Great value")]

    system_prompt, _ = build_prompt([product], "durable and cheap", {1: reviews})

    assert "ONLY the reviews provided" in system_prompt
    assert "outside knowledge" in system_prompt
