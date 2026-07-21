"""Mini retrieval eval for /compare: 5 hand-written requirements with expected winners.

Seeds 4 products with distinct review content in an isolated in-memory DB, embeds them
via the configured LLM, then runs get_recommendation() for each query and checks the
winner against expectation. Prints a hits/misses table.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.embed import embed_review, embed_texts, retrieve_relevant_reviews  # noqa: E402
from app.models import Base, Product, Review  # noqa: E402
from app.recommend import RecommendationParseError, get_recommendation  # noqa: E402
from app.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

PRODUCTS = {
    "TrailBlazer Hiking Shoe": [
        "Amazing grip on muddy trails, held up great in rain.",
        "Runs a bit narrow, sizing up helped.",
        "Sole is holding up after months of rough trail use.",
    ],
    "CloudWalk Comfort Sneaker": [
        "Super comfortable for all-day walking on pavement.",
        "Not enough support for actual trail running.",
        "Lightweight, barely notice I'm wearing them.",
    ],
    "SpeedRunner Racing Flat": [
        "Extremely lightweight and fast for race day.",
        "Got blisters after a long run, not much cushioning.",
        "Not durable enough for rough or rocky terrain.",
    ],
    "WinterTrek Boot": [
        "Excellent traction on ice and packed snow.",
        "Fully waterproof, kept my feet dry in slush.",
        "Heavy and stiff, takes a while to break in.",
    ],
}

EVAL_CASES = [
    ("Need shoes with great grip for muddy hiking trails", "TrailBlazer Hiking Shoe"),
    (
        "Most comfortable shoe for walking around town all day",
        "CloudWalk Comfort Sneaker",
    ),
    ("Want the lightest, fastest shoe for racing", "SpeedRunner Racing Flat"),
    ("Need something waterproof with good traction on ice and snow", "WinterTrek Boot"),
    (
        "Shoe with strong ankle support for technical trail running",
        "TrailBlazer Hiking Shoe",
    ),
]


def seed_products(db) -> list[Product]:
    products = []
    for name, review_texts in PRODUCTS.items():
        product = Product(name=name, price=99.99, rating=4.0)
        db.add(product)
        db.flush()
        for text in review_texts:
            review = Review(product_id=product.id, text=text)
            embed_review(review)
            db.add(review)
        products.append(product)
    db.commit()
    return products


def run_eval(products: list[Product]) -> list[dict]:
    rows = []
    for query, expected in EVAL_CASES:
        query_embedding = embed_texts([query])[0]
        reviews_by_product = {
            product.id: retrieve_relevant_reviews(
                product.reviews, query_embedding, settings.retrieval_top_k
            )
            for product in products
        }
        try:
            recommendation = get_recommendation(products, query, reviews_by_product)
            got, reason = recommendation.recommended_product, recommendation.reason
        except RecommendationParseError as exc:
            got, reason = "<parse error>", str(exc).splitlines()[0]
        rows.append(
            {
                "query": query,
                "expected": expected,
                "got": got,
                "hit": got == expected,
                "reason": reason,
            }
        )
    return rows


def print_table(rows: list[dict]) -> None:
    logger.info("%s", f"{'HIT':<5}{'query':<58}{'expected':<28}{'got':<28}")
    for row in rows:
        mark = "OK" if row["hit"] else "MISS"
        logger.info(
            "%s", f"{mark:<5}{row['query']:<58}{row['expected']:<28}{row['got']:<28}"
        )
    hits = sum(r["hit"] for r in rows)
    logger.info("%s", f"\n{hits}/{len(rows)} hits")


def main() -> None:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    products = seed_products(db)
    rows = run_eval(products)
    print_table(rows)

    logger.info("%s", "\n--- misses (reason given) ---")
    for row in rows:
        if not row["hit"]:
            logger.info("query: %s", row["query"])
            logger.info("  expected=%r got=%r", row["expected"], row["got"])
            logger.info("  model reason: %s", row["reason"])


if __name__ == "__main__":
    main()
