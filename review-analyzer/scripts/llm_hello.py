"""Standalone script: send one prompt to the configured LLM and inspect the response."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

from app.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": "Say hello in exactly five words."}],
    )

    logger.info("=== Full response object ===")
    logger.info("%s", response.model_dump_json(indent=2))

    logger.info("\n=== Located fields ===")
    logger.info("content: %r", response.choices[0].message.content)
    logger.info("model: %r", response.model)
    logger.info("usage.prompt_tokens: %s", response.usage.prompt_tokens)
    logger.info("usage.completion_tokens: %s", response.usage.completion_tokens)
    logger.info("usage.total_tokens: %s", response.usage.total_tokens)


if __name__ == "__main__":
    main()
