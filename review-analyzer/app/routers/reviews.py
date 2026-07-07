from fastapi import APIRouter

router = APIRouter()


@router.get("/reviews/{product_id}")
async def get_reviews(product_id: str):
    """Get reviews for a product."""
    return {
        "product_id": product_id,
        "reviews": [
            {
                "id": "1",
                "rating": 5,
                "text": "Great product!",
                "author": "User1",
            }
        ],
    }


@router.post("/reviews/{product_id}")
async def create_review(product_id: str, rating: int, text: str):
    """Create a new review for a product."""
    return {
        "product_id": product_id,
        "rating": rating,
        "text": text,
        "status": "created",
    }
