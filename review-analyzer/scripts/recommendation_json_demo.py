"""Prompt for strict JSON matching a recommendation schema; parse it; handle disobedience."""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402

from app.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)


class ProductRecommendation(BaseModel):
    recommend: bool
    confidence: float = Field(ge=0, le=1)
    summary: str
    pros: list[str]
    cons: list[str]


SYSTEM_PROMPT = f"""You are a product recommendation engine.
Respond ONLY with JSON matching exactly this schema, and nothing else \
(no markdown fences, no prose before or after):

{json.dumps(ProductRecommendation.model_json_schema(), indent=2)}
"""

REVIEWS_TEXT = """
Reviews for "Mechanical Keyboard X200":
1. "Switches feel great, but the keycaps started chipping after two weeks."
2. "Best keyboard I've owned. Loud but satisfying."
3. "Backlight died on day 3. Sent it back."
4. "Solid build, a bit heavy for travel."
"""


class RecommendationParseError(Exception):
    """Raised when the model's output can't be parsed into ProductRecommendation."""


def parse_recommendation(raw_content: str) -> ProductRecommendation:
    """Parse model output into ProductRecommendation, with a clear error path on failure."""
    text = raw_content.strip()
    # Models sometimes wrap JSON in markdown fences despite instructions not to.
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
        return ProductRecommendation.model_validate(data)
    except ValidationError as exc:
        raise RecommendationParseError(
            f"JSON did not match the recommendation schema: {exc}\n--- raw output ---\n{raw_content}"
        ) from exc


def run_live_demo(client: OpenAI) -> None:
    logger.info("=== Live run: model asked for strict JSON ===")
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": REVIEWS_TEXT},
        ],
    )
    raw_content = response.choices[0].message.content
    logger.info("raw model output:\n%s\n", raw_content)

    try:
        recommendation = parse_recommendation(raw_content)
        logger.info("Parsed into ProductRecommendation:")
        logger.info("%s", recommendation.model_dump_json(indent=2))
    except RecommendationParseError as exc:
        logger.info("[handled] Could not parse model output:\n%s", exc)


def run_malformed_demo() -> None:
    logger.info("\n=== Deterministic malformed-JSON case ===")
    malformed = (
        'Sure! Here is the recommendation:\n{"recommend": true, "confidence": 0.9, '
    )
    logger.info("raw model output:\n%s\n", malformed)

    try:
        parse_recommendation(malformed)
        logger.error("ERROR: expected parsing to fail but it didn't")
    except RecommendationParseError as exc:
        logger.info("[handled] Could not parse model output:\n%s", exc)


def main() -> None:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    run_live_demo(client)
    run_malformed_demo()


if __name__ == "__main__":
    main()
