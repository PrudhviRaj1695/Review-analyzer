"""Build LLM prompts and parse product recommendations from reviews."""
import json
import logging

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.models import Product
from app.settings import settings

logger = logging.getLogger(__name__)


class RecommendationParseError(Exception):
    """Raised when the model's output can't be parsed into a recommendation."""


def get_llm_client() -> OpenAI:
    """Build the configured LLM client (chat + embeddings share these settings)."""
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """Cost of one call at settings' configured per-1M-token prices."""
    return (
        prompt_tokens * settings.llm_input_price_per_1m
        + completion_tokens * settings.llm_output_price_per_1m
    ) / 1_000_000


class LLMRecommendation(BaseModel):
    """Schema the LLM must fill in."""

    recommended_product: str
    reason: str
    main_positive: str
    main_complaint: str
    confidence: float = Field(ge=0, le=1)


EXAMPLE_RESPONSE = {
    "recommended_product": "Example Product Name",
    "reason": "One or two sentences on why this product best fits the requirement.",
    "main_positive": "The strongest positive point raised across its reviews.",
    "main_complaint": "The most common complaint in its reviews, or 'none' if there isn't one.",
    "confidence": 0.8,
}


def build_prompt(
    products: list[Product], requirement: str, reviews_by_product: dict[int, list]
) -> tuple[str, str]:
    """Build the (system, user) prompts for a product comparison.

    reviews_by_product maps product.id -> the reviews retrieved for it (a subset,
    not necessarily all of the product's reviews).
    """
    system_prompt = (
        "You are a product recommendation engine.\n"
        "Given a shopper's requirement and a set of products with their retrieved "
        "customer reviews, pick exactly ONE product that best fits the requirement.\n\n"
        "Use ONLY the reviews provided below. Do not use any outside knowledge about "
        "these or similar products, and do not invent details the reviews don't "
        "contain. If the reviews don't give enough information, say so honestly in "
        "your reason instead of guessing.\n\n"
        "Match the requirement's specific conditions (terrain, weather, activity, use "
        "case) to reviews about those SAME conditions. Superficially similar words are "
        "not the same thing — e.g. 'traction on ice' does not satisfy a requirement "
        "about 'grip in mud', and 'comfortable for walking' does not satisfy a "
        "requirement about running support. Prefer the product whose reviews name the "
        "exact condition asked about.\n\n"
        "Respond with ONLY a single JSON object filled in with your own values, "
        "using exactly this shape (no markdown fences, no extra text before or "
        "after, and do not copy the example values verbatim):\n\n"
        f"{json.dumps(EXAMPLE_RESPONSE, indent=2)}\n\n"
        "confidence must be a number between 0 and 1."
    )

    user_prompt = f"Shopper requirement: {requirement}\n\n" + build_context(
        products, reviews_by_product
    )

    return system_prompt, user_prompt


def format_product_context(product: Product, reviews: list) -> str:
    """One human-readable, labelled block: product name/id/price/rating + its reviews."""
    review_lines = (
        "\n".join(f"- {review.text}" for review in reviews)
        or "- (no reviews retrieved)"
    )
    return (
        f'Product: "{product.name}" (id={product.id}, price={product.price}, '
        f"rating={product.rating})\nReviews:\n{review_lines}"
    )


def build_context(products: list[Product], reviews_by_product: dict[int, list]) -> str:
    """Join per-product context blocks, hard-capped at settings.llm_context_max_chars."""
    context = "\n\n".join(
        format_product_context(product, reviews_by_product.get(product.id, []))
        for product in products
    )
    max_chars = settings.llm_context_max_chars
    if len(context) > max_chars:
        context = context[:max_chars] + "\n...[truncated]"
    return context


def parse_recommendation(raw_content: str) -> LLMRecommendation:
    """Parse model output into LLMRecommendation, with a clear error path on failure."""
    text = raw_content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecommendationParseError(
            f"Model did not return valid JSON: {exc}\n--- raw output ---\n{raw_content}"
        ) from exc

    try:
        return LLMRecommendation.model_validate(data)
    except ValidationError as exc:
        raise RecommendationParseError(
            f"JSON did not match the recommendation schema: {exc}\n--- raw output ---\n{raw_content}"
        ) from exc


def get_recommendation(
    products: list[Product], requirement: str, reviews_by_product: dict[int, list]
) -> LLMRecommendation:
    """Call the LLM and return a parsed recommendation, grounded only in reviews_by_product."""
    client = get_llm_client()
    system_prompt, user_prompt = build_prompt(products, requirement, reviews_by_product)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_content = response.choices[0].message.content

    usage = response.usage
    if usage is not None:
        cost_usd = estimate_cost_usd(usage.prompt_tokens, usage.completion_tokens)
        logger.info(
            "compare LLM call: model=%s prompt_tokens=%d completion_tokens=%d "
            "total_tokens=%d cost_usd=%.6f",
            settings.llm_model,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            cost_usd,
        )

    return parse_recommendation(raw_content)
