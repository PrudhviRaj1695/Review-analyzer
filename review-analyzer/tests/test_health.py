"""Test suite for product endpoints - database-backed."""


def test_health_check(client):
    """Test that API is running."""
    # ARRANGE - no setup needed

    # ACT
    response = client.get("/")

    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "status" in data


def test_get_empty_products_list(client):
    """Test getting products when database is empty."""
    # ARRANGE - fixture ensures clean database

    # ACT
    response = client.get("/products")

    # ASSERT
    assert response.status_code == 200
    assert response.json() == []


def test_create_product_success(client):
    """Test successfully creating a product and persisting to database."""
    # ARRANGE - fixture ensures clean database
    product_data = {
        "Product_id": 1,
        "Product_name": "Laptop",
        "Product_description": "A powerful laptop for work",
        "product_review": "Great quality and performance",
        "product_rating": 4.5,
        "product_price": 999.99,
    }

    # ACT
    response = client.post("/products", json=product_data)

    # ASSERT
    assert response.status_code == 201
    assert response.json() == {"message": "Product review added successfully!"}


def test_get_product_after_creation(client):
    """Test that product created is persisted and retrievable from database."""
    # ARRANGE - fixture ensures clean database
    product_data = {
        "Product_id": 2,
        "Product_name": "Phone",
        "Product_description": "Smartphone with great camera",
        "product_review": "Excellent phone",
        "product_rating": 4.8,
        "product_price": 799.99,
    }

    # ACT - Create product (goes to database)
    client.post("/products", json=product_data)

    # ACT - Retrieve product (reads from database)
    response = client.get("/products/2")

    # ASSERT - Product is in database
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["Product_name"] == "Phone"
    assert float(data["product_price"]) == 799.99


def test_get_product_not_found(client):
    """Test getting a product that doesn't exist in database."""
    # ARRANGE - fixture ensures clean database
    product_id = 999

    # ACT
    response = client.get(f"/products/{product_id}")

    # ASSERT
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_duplicate_product_fails(client):
    """Test that creating a product with duplicate ID fails."""
    # ARRANGE - fixture ensures clean database
    product_data = {
        "Product_id": 3,
        "Product_name": "Keyboard",
        "Product_description": "Mechanical keyboard",
        "product_review": "Great typing experience",
        "product_rating": 4.7,
        "product_price": 149.99,
    }

    # ACT - Create first product
    response1 = client.post("/products", json=product_data)
    assert response1.status_code == 201

    # ACT - Try to create duplicate (same ID)
    response2 = client.post("/products", json=product_data)

    # ASSERT - Second create fails with 400
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


def test_submit_reviews_success(client):
    """Test submitting reviews endpoint."""
    # ARRANGE
    reviews_data = {
        "reviews": ["Great product!", "Amazing quality", "Highly recommend"]
    }

    # ACT
    response = client.post("/products/reviews", json=reviews_data)

    # ASSERT
    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert len(response.json()["reviews"]) == 3


def test_list_multiple_products(client):
    """Test listing multiple products from database."""
    # ARRANGE - fixture ensures clean database
    products_data = [
        {
            "Product_id": 1,
            "Product_name": "Laptop",
            "Product_description": "Powerful laptop",
            "product_review": "Great!",
            "product_rating": 4.5,
            "product_price": 999.99,
        },
        {
            "Product_id": 2,
            "Product_name": "Mouse",
            "Product_description": "Wireless mouse",
            "product_review": "Good!",
            "product_rating": 4.0,
            "product_price": 29.99,
        },
    ]

    # ACT - Create multiple products
    for product_data in products_data:
        response = client.post("/products", json=product_data)
        assert response.status_code == 201

    # ACT - List all products
    response = client.get("/products")

    # ASSERT
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 2
    assert products[0]["Product_name"] == "Laptop"
    assert products[1]["Product_name"] == "Mouse"
    # Verify review_count is included
    assert "review_count" in products[0]
    assert products[0]["review_count"] == 0


def test_create_review_success(client):
    """Test successfully creating a review for an existing product."""
    # ARRANGE - Create product first
    product_data = {
        "Product_id": 1,
        "Product_name": "Laptop",
        "Product_description": "Powerful laptop for work",
        "product_review": "Excellent quality",
        "product_rating": 4.5,
        "product_price": 999.99,
    }
    response = client.post("/products", json=product_data)
    assert response.status_code == 201

    # ACT - Create review for the product
    review_data = {
        "product_id": 1,
        "text": "This laptop is amazing! Fast, reliable, and great build quality.",
    }
    response = client.post("/products/reviews/create", json=review_data)

    # ASSERT - Review created successfully with FK
    assert response.status_code == 201
    review = response.json()
    assert review["product_id"] == 1  # FK correctly set
    assert (
        review["text"]
        == "This laptop is amazing! Fast, reliable, and great build quality."
    )
    assert "id" in review
    assert "created_at" in review


def test_create_review_invalid_product_returns_404(client):
    """Test that creating review for non-existent product returns 404 BEFORE insert.

    This validates the FK constraint at application level.
    """
    # ARRANGE - No product created, database is empty

    # ACT - Try to create review for non-existent product ID 999
    review_data = {
        "product_id": 999,
        "text": "This review should not be created",
    }
    response = client.post("/products/reviews/create", json=review_data)

    # ASSERT - Request rejected with 404 before database insert
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_product_includes_review_count(client):
    """Test that product response includes review_count via relationship."""
    # ARRANGE - Create product and add reviews
    product_data = {
        "Product_id": 1,
        "Product_name": "Phone",
        "Product_description": "Smartphone with great camera",
        "product_review": "Amazing device",
        "product_rating": 4.8,
        "product_price": 799.99,
    }
    response = client.post("/products", json=product_data)
    assert response.status_code == 201

    # Add 3 reviews
    for i in range(3):
        review_data = {
            "product_id": 1,
            "text": f"Review #{i + 1}: Great product!",
        }
        response = client.post("/products/reviews/create", json=review_data)
        assert response.status_code == 201

    # ACT - Get the product
    response = client.get("/products/1")

    # ASSERT - Product includes review_count
    assert response.status_code == 200
    product = response.json()
    assert product["review_count"] == 3  # Relationship counted correctly


def test_get_product_reviews(client):
    """Test getting all reviews for a specific product."""
    # ARRANGE - Create product and add reviews
    product_data = {
        "Product_id": 1,
        "Product_name": "Keyboard",
        "Product_description": "Mechanical keyboard for gaming",
        "product_review": "Excellent typing",
        "product_rating": 4.7,
        "product_price": 149.99,
    }
    response = client.post("/products", json=product_data)
    assert response.status_code == 201

    reviews_to_add = [
        "Best keyboard I've ever used!",
        "Excellent typing experience",
        "Highly recommend for gaming",
    ]

    for review_text in reviews_to_add:
        review_data = {
            "product_id": 1,
            "text": review_text,
        }
        response = client.post("/products/reviews/create", json=review_data)
        assert response.status_code == 201

    # ACT - Get all reviews for product
    response = client.get("/products/1/reviews")

    # ASSERT - All reviews returned
    assert response.status_code == 200
    reviews = response.json()
    assert len(reviews) == 3
    assert reviews[0]["text"] == "Best keyboard I've ever used!"
    assert reviews[1]["text"] == "Excellent typing experience"
    assert reviews[2]["text"] == "Highly recommend for gaming"
    # Verify FK is correct for all reviews
    for review in reviews:
        assert review["product_id"] == 1


def test_get_reviews_for_nonexistent_product(client):
    """Test that getting reviews for non-existent product returns 404."""
    # ARRANGE - No products in database

    # ACT
    response = client.get("/products/999/reviews")

    # ASSERT
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_transaction_rollback_on_error(db):
    """
    Test that transactions rollback on error - demonstrating ALL-OR-NOTHING.

    Scenario: Intentionally fail mid-transaction to show rollback.
    This proves that if an error occurs, NO partial data is written.
    """
    # ARRANGE
    from app.models import Product, Review

    # Verify database starts empty
    assert db.query(Product).count() == 0
    assert db.query(Review).count() == 0

    # ACT - Try to create product + review, but force error mid-way
    try:
        # Start implicit transaction
        product = Product(id=1, name="Test Product", price=99.99, rating=4.0)
        db.add(product)
        db.flush()  # Write to transaction buffer (not committed yet)

        # At this point, product exists in transaction but not in database
        assert db.query(Product).count() == 1  # Visible within transaction

        # Now force an error BEFORE commit
        raise RuntimeError("Intentional error to trigger rollback!")

    except RuntimeError:
        # Error caught, transaction should rollback
        db.rollback()

    # ASSERT - Verify NO data was written (all-or-nothing)
    # Product should NOT exist because error happened before commit
    assert db.query(Product).count() == 0
    assert db.query(Review).count() == 0

    # This proves: If ANY step fails, ENTIRE transaction rolls back
    # No orphaned products without reviews


def test_successful_transaction_commits_all_data(db):
    """
    Test that successful transactions commit ALL data together.

    Demonstrates the opposite: when everything succeeds, all data is written.
    """
    # ARRANGE
    from app.models import Product, Review

    # Verify database starts empty
    assert db.query(Product).count() == 0

    # ACT - Create product successfully
    product = Product(id=1, name="Laptop", price=999.99, rating=4.5)
    db.add(product)
    db.commit()  # Explicitly commit

    # Add review in same transaction
    review = Review(product_id=1, text="Excellent product!")
    db.add(review)
    db.commit()  # Explicitly commit

    # ASSERT - All data was written
    assert db.query(Product).count() == 1
    assert db.query(Review).count() == 1

    # Verify relationship works
    product = db.query(Product).first()
    assert len(product.reviews) == 1
    assert product.reviews[0].text == "Excellent product!"
