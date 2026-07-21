import logging

from app.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


def main():
    logger.info("Hello from review-analyzer!")


if __name__ == "__main__":
    main()
