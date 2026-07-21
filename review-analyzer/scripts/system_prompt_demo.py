"""Same question, three system prompts. Compare how the system message steers behavior."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

from app.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

QUESTION = "How do I center a div in CSS?"

SYSTEM_PROMPTS = {
    "neutral": "You are a helpful assistant.",
    "terse_expert": (
        "You are a senior engineer. Answer in exactly one sentence. "
        "No greetings, no explanations, no caveats."
    ),
    "beginner_teacher": (
        "You are a patient teacher explaining to someone who has never coded before. "
        "Use a real-world analogy before giving any code."
    ),
}


def run(client: OpenAI, system_prompt: str) -> str:
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": QUESTION},
        ],
    )
    return response.choices[0].message.content


def main() -> None:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    logger.info("User question (identical in all 3 runs): %r\n", QUESTION)

    results = {}
    for name, system_prompt in SYSTEM_PROMPTS.items():
        results[name] = run(client, system_prompt)

    for name, system_prompt in SYSTEM_PROMPTS.items():
        logger.info("--- %s ---", name)
        logger.info("system: %r", system_prompt)
        logger.info("response: %r", results[name])
        logger.info("")


if __name__ == "__main__":
    main()
