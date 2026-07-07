from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Annotated


class ReviewsIn(BaseModel):
    reviews: list[str] = Field(min_length=1, max_length=50)


NonEmptyReview = Annotated[str, Field(min_length=1)]


class Product(BaseModel):
    Product_id: int
    Product_name: str = Field(min_length=2, max_length=10)
    Product_description: str = Field(min_length=5, max_length=100)
    product_review: str = Field(min_length=5, max_length=100)
    product_rating: float
    product_price: float


class ProductOut(BaseModel):
    id: int
    Product_name: str
    Product_description: str
    product_review: str | None = None
    product_rating: float
    product_price: float


router = APIRouter(prefix="/products")

products: list[Product] = []


@router.post("/reviews")
def submit_reviews(payload: ReviewsIn):
    return {"count": len(payload.reviews), "reviews": payload.reviews}


@router.post("", status_code=201)
def create_product(product: Product):
    product_ids = [p.Product_id for p in products]
    if product.Product_id in product_ids:
        raise HTTPException(
            status_code=400, detail="Product with this ID already exists!"
        )
    products.append(product)

    return {"message": "Product review added successfully!"}


@router.get("", response_model=list[ProductOut])
def list_products():
    return [
        ProductOut(
            id=product.Product_id,
            Product_name=product.Product_name,
            Product_description=product.Product_description,
            product_review=product.product_review,
            product_rating=product.product_rating,
            product_price=product.product_price,
        )
        for product in products
    ]


@router.get("/{p_id}", response_model=ProductOut)
def get_product_review(p_id: int):
    for product in products:
        if product.Product_id == p_id:
            return ProductOut(
                id=product.Product_id,
                Product_name=product.Product_name,
                Product_description=product.Product_description,
                product_review=product.product_review,
                product_rating=product.product_rating,
                product_price=product.product_price,
            )

    raise HTTPException(status_code=404, detail="Product review not found!")
