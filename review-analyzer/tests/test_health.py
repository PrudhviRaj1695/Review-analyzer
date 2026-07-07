from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test that API is running"""
    # ARRANGE
    # (no setup needed - fixture resets state)

    # ACT
    response = client.get("/")

    # ASSERT
    assert response.status_code == 200
    assert response.json() == {"message": "API is running successfully!"}


def test_get_empty_products_list():
    """Test getting products when list is empty"""
    # ARRANGE - fixture ensures list is empty

    # ACT
    response = client.get("/products")

    # ASSERT
    assert response.status_code == 200
    assert response.json() == []


def test_create_product_success():
    """Test successfully creating a product"""
    # ARRANGE - fixture resets products list
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


def test_get_product_after_creation():
    """Test getting a product after creating it"""
    # ARRANGE - fixture ensures clean state
    product_data = {
        "Product_id": 2,
        "Product_name": "Phone",
        "Product_description": "Smartphone with great camera",
        "product_review": "Excellent phone",
        "product_rating": 4.8,
        "product_price": 799.99,
    }

    # ACT - Create product
    client.post("/products", json=product_data)

    # ACT - Retrieve product
    response = client.get("/products/2")

    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["Product_name"] == "Phone"


def test_get_product_not_found():
    """Test getting a product that doesn't exist"""
    # ARRANGE - fixture resets list (empty)
    product_id = 999

    # ACT
    response = client.get(f"/products/{product_id}")

    # ASSERT
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_submit_reviews_success():
    """Test submitting reviews"""
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


def test_create_product_with_mocked_id(monkeypatch):
    """Test creating a product with a mocked/deterministic ID generator"""

    # ARRANGE - Mock the ID generator
    def mock_id_generator():
        return "test-id-12345"  # Always returns same value

    # Replace the real function with our mock
    monkeypatch.setattr("app.utils.generate_product_id", mock_id_generator)

    # ACT
    product_data = {
        "Product_id": 1,
        "Product_name": "Laptop",
        "Product_description": "A powerful laptop",
        "product_review": "Great quality",
        "product_rating": 4.5,
        "product_price": 999.99,
    }
    response = client.post("/products", json=product_data)

    # ASSERT
    assert response.status_code == 201
    # Now we know exactly what ID was generated!
