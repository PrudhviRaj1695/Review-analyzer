from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base, relationship

EMBEDDING_DIM = 1536  # text-embedding-3-small

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    rating = Column(Numeric(3, 2))

    # Relationship: one product has many reviews
    # back_populates creates bidirectional access
    reviews = relationship(
        "Review", back_populates="product", cascade="all, delete-orphan"
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    # Relationship: many reviews belong to one product
    # back_populates="reviews" links back to Product.reviews
    product = relationship("Product", back_populates="reviews")
