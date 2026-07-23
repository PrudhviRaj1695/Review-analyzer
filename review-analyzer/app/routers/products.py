import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product as ProductModel, Review as ReviewModel

logger = logging.getLogger(__name__)


class ReviewsIn(BaseModel):
    reviews: list[str] = Field(min_length=1, max_length=50)


NonEmptyReview = Annotated[str, Field(min_length=1)]


class ProductIn(BaseModel):
    """Input model for creating products (from client)."""

    Product_id: int
    Product_name: str = Field(min_length=2, max_length=100)
    Product_description: str = Field(min_length=5, max_length=500)
    product_review: str = Field(min_length=5, max_length=500)
    product_rating: float = Field(ge=0, le=5)
    product_price: float = Field(gt=0)


class ProductOut(BaseModel):
    """Output model for returning products (to client)."""

    id: int
    Product_name: str
    Product_description: str
    product_review: str | None = None
    product_rating: float
    product_price: float
    review_count: int = 0  # Number of reviews for this product


class ReviewIn(BaseModel):
    """Input model for creating a review."""

    product_id: int
    text: str = Field(min_length=1, max_length=1000)


class ReviewOut(BaseModel):
    """Output model for returning a review."""

    id: int
    product_id: int
    text: str
    created_at: str  # ISO format timestamp


router = APIRouter(prefix="/products")


@router.post("/reviews")
def submit_reviews(payload: ReviewsIn):
    """Submit multiple reviews."""
    return {"count": len(payload.reviews), "reviews": payload.reviews}


@router.post("", status_code=201)
def create_product(product: ProductIn, db: Session = Depends(get_db)):
    """
    Create a new product and save to database.

    The product data is converted from the input model to a database model
    and persisted in PostgreSQL.
    """
    # Create ORM model from input
    db_product = ProductModel(
        id=product.Product_id,
        name=product.Product_name,
        price=product.product_price,
        rating=product.product_rating,
    )

    # Check if product with this ID already exists
    existing = (
        db.query(ProductModel).filter(ProductModel.id == product.Product_id).first()
    )

    if existing:
        raise HTTPException(
            status_code=400, detail="Product with this ID already exists!"
        )

    # Add to database and save
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    logger.info("Product created: id=%s name=%s", db_product.id, db_product.name)

    return {"message": "Product review added successfully!"}


@router.get("")
def list_products(db: Session = Depends(get_db)):
    """
    List all products from the database.

    Query the products table and return as list of ProductOut models.
    Includes review count for each product via the relationship.
    """
    db_products = db.query(ProductModel).all()

    return [
        ProductOut(
            id=product.id,
            Product_name=product.name,
            Product_description="",
            product_review="",
            product_rating=float(product.rating or 0),
            product_price=float(product.price),
            review_count=len(product.reviews),  # Use relationship to count reviews
        )
        for product in db_products
    ]


@router.get("/{p_id}")
def get_product_review(p_id: int, db: Session = Depends(get_db)):
    """
    Get a single product by ID from the database.

    If product doesn't exist, return 404.
    Includes review count via the relationship.
    """
    db_product = db.query(ProductModel).filter(ProductModel.id == p_id).first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product review not found!")

    return ProductOut(
        id=db_product.id,
        Product_name=db_product.name,
        Product_description="",
        product_review="",
        product_rating=float(db_product.rating or 0),
        product_price=float(db_product.price),
        review_count=len(db_product.reviews),  # Use relationship to count reviews
    )


@router.post("/reviews/create", status_code=201)
def create_review(review: ReviewIn, db: Session = Depends(get_db)):
    """
    Create a new review for a product.

    Validates:
    1. Product with product_id exists (before INSERT)
    2. Returns 404 if product doesn't exist (prevents orphan reviews via FK check)

    The review is saved with correct product_id foreign key.
    SQLAlchemy automatically enforces the FK constraint.
    """
    # Validate product exists BEFORE trying to insert review
    db_product = (
        db.query(ProductModel).filter(ProductModel.id == review.product_id).first()
    )

    if not db_product:
        raise HTTPException(
            status_code=404, detail=f"Product with ID {review.product_id} not found!"
        )

    # Create review ORM model
    # product_id is set from the review input (validated above)
    db_review = ReviewModel(
        product_id=review.product_id,
        text=review.text,
    )

    # Insert into database
    db.add(db_review)
    db.commit()
    db.refresh(db_review)

    return ReviewOut(
        id=db_review.id,
        product_id=db_review.product_id,
        text=db_review.text,
        created_at=db_review.created_at.isoformat() if db_review.created_at else None,
    )


@router.get("/{p_id}/reviews")
def get_product_reviews(p_id: int, db: Session = Depends(get_db)):
    """
    Get all reviews for a specific product.

    Returns 404 if product doesn't exist.
    Uses the relationship to fetch all reviews for this product.
    """
    db_product = db.query(ProductModel).filter(ProductModel.id == p_id).first()

    if not db_product:
        raise HTTPException(
            status_code=404, detail=f"Product with ID {p_id} not found!"
        )

    # Access reviews via the relationship
    reviews = db_product.reviews

    return [
        ReviewOut(
            id=review.id,
            product_id=review.product_id,
            text=review.text,
            created_at=review.created_at.isoformat() if review.created_at else None,
        )
        for review in reviews
    ]
