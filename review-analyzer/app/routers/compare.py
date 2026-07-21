import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.embed import embed_texts, retrieve_relevant_reviews
from app.models import Product as ProductModel
from app.recommend import RecommendationParseError, get_recommendation
from app.settings import settings

logger = logging.getLogger(__name__)


class CompareRequest(BaseModel):
    """Input model for comparing products."""

    product_ids: list[int] = Field(min_length=1, max_length=10)
    requirement: str = Field(min_length=1, max_length=500)


class CompareResponse(BaseModel):
    """Output model for a product recommendation."""

    recommended_product: str
    reason: str
    main_positive: str
    main_complaint: str
    confidence: float


router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
def compare_products(payload: CompareRequest, db: Session = Depends(get_db)):
    """
    Compare products against a shopper requirement and return an LLM recommendation.

    Loads the requested products from the DB, embeds the requirement, retrieves each
    product's top-k most relevant reviews by embedding similarity, and asks the
    configured LLM to pick the best fit using only those retrieved reviews.
    """
    products = (
        db.query(ProductModel).filter(ProductModel.id.in_(payload.product_ids)).all()
    )

    found_ids = {product.id for product in products}
    missing_ids = set(payload.product_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Product(s) not found: {sorted(missing_ids)}",
        )

    try:
        query_embedding = embed_texts([payload.requirement])[0]
        reviews_by_product = {
            product.id: retrieve_relevant_reviews(
                product.reviews, query_embedding, settings.retrieval_top_k
            )
            for product in products
        }
        recommendation = get_recommendation(
            products, payload.requirement, reviews_by_product
        )
    except RecommendationParseError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned an unparseable recommendation: {exc}",
        ) from exc
    except APIError as exc:
        logger.exception("LLM provider call failed")
        raise HTTPException(
            status_code=503,
            detail="Recommendation service is temporarily unavailable. Please try again shortly.",
        ) from exc

    return CompareResponse(**recommendation.model_dump())
