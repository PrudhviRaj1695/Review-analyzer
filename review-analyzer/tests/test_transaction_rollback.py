"""
Test transaction rollback behavior: all-or-nothing writes.

Demonstrates that when an error occurs mid-transaction, the entire
transaction is rolled back, leaving no partial data written to the database.
"""
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Product, Review


def test_transaction_rollback_on_foreign_key_violation(db):
    """
    Deliberate failure: try to write a review with non-existent product_id.

    What happens:
    1. Create a product and add it (succeeds)
    2. Try to add a review with invalid product_id in same transaction
    3. Foreign key constraint fails
    4. Entire transaction rolls back
    5. Neither product nor review exist in the database

    This proves the all-or-nothing guarantee of transactions.
    """
    # Check initial state: database is empty
    initial_product_count = db.query(Product).count()
    initial_review_count = db.query(Review).count()
    assert initial_product_count == 0, "Database should start empty"
    assert initial_review_count == 0, "Database should start empty"

    # Start a transaction and deliberately cause an error mid-write
    try:
        # Write 1: Create a product (pending, not yet committed)
        product = Product(name="Test Product", price=99.99, rating=4.5)
        db.add(product)
        db.flush()  # Push to database, but don't commit yet
        print(f"[OK] Product added to transaction (ID will be: {product.id})")

        # Verify the product exists within the transaction
        tx_product_count = db.query(Product).count()
        assert tx_product_count == 1, "Product should exist in open transaction"
        print(f"     Within transaction: {tx_product_count} product(s) exist")

        # Write 2: Try to create a review with INVALID product_id
        # This should fail because product_id=9999 doesn't exist
        bad_review = Review(product_id=9999, text="This will fail")
        db.add(bad_review)
        db.flush()  # This will raise IntegrityError

        # Should never reach here
        pytest.fail("Expected IntegrityError was not raised")

    except IntegrityError as e:
        # Error occurred mid-transaction
        print(f"[ERROR] Error caught (as expected): {type(e).__name__}")
        print("        Foreign key constraint violation")

        # Rollback the entire transaction
        db.rollback()
        print("        Transaction rolled back")

    # After rollback: verify NO data was written
    final_product_count = db.query(Product).count()
    final_review_count = db.query(Review).count()

    print("\nAfter rollback:")
    print(f"  Products: {final_product_count} (should be 0)")
    print(f"  Reviews: {final_review_count} (should be 0)")

    assert (
        final_product_count == 0
    ), "Product should NOT exist after rollback (all-or-nothing)"
    assert (
        final_review_count == 0
    ), "Review should NOT exist after rollback (all-or-nothing)"


def test_transaction_commit_requires_all_operations_valid(db):
    """
    Contrast: when all operations are valid, commit succeeds.

    This shows the difference:
    - Valid transaction: all writes persist after commit
    - Invalid transaction: zero writes persist after rollback
    """
    # Scenario: Create product, then create review for that product
    try:
        # Both writes are valid
        product = Product(name="Valid Product", price=49.99, rating=4.0)
        db.add(product)
        db.flush()

        review = Review(product_id=product.id, text="Great product!")
        db.add(review)
        db.flush()

        print("[OK] Both operations valid")
        print(f"     Product ID: {product.id}")
        print(f"     Review references product {review.product_id}")

        # Commit succeeds
        db.commit()
        print("     Transaction committed")

    except IntegrityError:
        db.rollback()
        pytest.fail("Valid transaction should not fail")

    # After commit: both records should exist
    final_product_count = db.query(Product).count()
    final_review_count = db.query(Review).count()

    print("\nAfter commit:")
    print(f"  Products: {final_product_count} (should be 1)")
    print(f"  Reviews: {final_review_count} (should be 1)")

    assert final_product_count == 1, "Product should persist after commit"
    assert final_review_count == 1, "Review should persist after commit"


def test_multiple_products_with_one_failure_rolls_back_all(db):
    """
    Multi-write scenario: add 3 products, then fail on the 3rd's review.

    Demonstrates that rollback is transaction-wide, not selective.
    All writes (even ones that succeeded) are undone.
    """
    try:
        products = []

        # Add 3 products
        for i in range(1, 4):
            p = Product(name=f"Product {i}", price=10.0 * i, rating=3.0 + i * 0.5)
            db.add(p)
            db.flush()
            products.append(p)
            print(f"[OK] Added Product {i} (ID: {p.id})")

        # Add reviews for products 1 and 2 (valid)
        for i in range(2):
            r = Review(product_id=products[i].id, text=f"Review for product {i+1}")
            db.add(r)
            db.flush()
            print(f"[OK] Added review for Product {i+1}")

        # Try to add review for product with invalid ID (fail on 3rd review)
        print("[FAIL] Attempting review with invalid product_id...")
        bad_review = Review(product_id=9999, text="This will fail")
        db.add(bad_review)
        db.flush()  # Raises IntegrityError

        pytest.fail("Expected error not raised")

    except IntegrityError:
        print("       IntegrityError raised as expected")
        db.rollback()
        print("       Entire transaction rolled back")

    # After rollback: ALL writes are undone
    final_product_count = db.query(Product).count()
    final_review_count = db.query(Review).count()

    print("\nAfter rollback:")
    print(f"  Products: {final_product_count} (should be 0, not 3)")
    print(f"  Reviews: {final_review_count} (should be 0, not 2)")

    assert (
        final_product_count == 0
    ), "No products should exist after rollback (all 3 undone)"
    assert (
        final_review_count == 0
    ), "No reviews should exist after rollback (all 2 undone)"
    print("\n[OK] Atomic: all writes rolled back together, none left behind")
