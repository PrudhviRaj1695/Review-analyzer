"""
Test transaction rollback behavior: all-or-nothing writes.

Demonstrates that when an error occurs mid-transaction, the entire
transaction is rolled back, leaving no partial data written to the database.
"""
import logging

import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Product, Review

logger = logging.getLogger(__name__)


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
        logger.info("[OK] Product added to transaction (ID will be: %s)", product.id)

        # Verify the product exists within the transaction
        tx_product_count = db.query(Product).count()
        assert tx_product_count == 1, "Product should exist in open transaction"
        logger.info("     Within transaction: %s product(s) exist", tx_product_count)

        # Write 2: Try to create a review with INVALID product_id
        # This should fail because product_id=9999 doesn't exist
        bad_review = Review(product_id=9999, text="This will fail")
        db.add(bad_review)
        db.flush()  # This will raise IntegrityError

        # Should never reach here
        pytest.fail("Expected IntegrityError was not raised")

    except IntegrityError as e:
        # Error occurred mid-transaction
        logger.error("[ERROR] Error caught (as expected): %s", type(e).__name__)
        logger.error("        Foreign key constraint violation")

        # Rollback the entire transaction
        db.rollback()
        logger.error("        Transaction rolled back")

    # After rollback: verify NO data was written
    final_product_count = db.query(Product).count()
    final_review_count = db.query(Review).count()

    logger.info("\nAfter rollback:")
    logger.info("  Products: %s (should be 0)", final_product_count)
    logger.info("  Reviews: %s (should be 0)", final_review_count)

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

        logger.info("[OK] Both operations valid")
        logger.info("     Product ID: %s", product.id)
        logger.info("     Review references product %s", review.product_id)

        # Commit succeeds
        db.commit()
        logger.info("     Transaction committed")

    except IntegrityError:
        db.rollback()
        pytest.fail("Valid transaction should not fail")

    # After commit: both records should exist
    final_product_count = db.query(Product).count()
    final_review_count = db.query(Review).count()

    logger.info("\nAfter commit:")
    logger.info("  Products: %s (should be 1)", final_product_count)
    logger.info("  Reviews: %s (should be 1)", final_review_count)

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
            logger.info("[OK] Added Product %s (ID: %s)", i, p.id)

        # Add reviews for products 1 and 2 (valid)
        for i in range(2):
            r = Review(product_id=products[i].id, text=f"Review for product {i+1}")
            db.add(r)
            db.flush()
            logger.info("[OK] Added review for Product %s", i + 1)

        # Try to add review for product with invalid ID (fail on 3rd review)
        logger.warning("[FAIL] Attempting review with invalid product_id...")
        bad_review = Review(product_id=9999, text="This will fail")
        db.add(bad_review)
        db.flush()  # Raises IntegrityError

        pytest.fail("Expected error not raised")

    except IntegrityError:
        logger.info("       IntegrityError raised as expected")
        db.rollback()
        logger.info("       Entire transaction rolled back")

    # After rollback: ALL writes are undone
    final_product_count = db.query(Product).count()
    final_review_count = db.query(Review).count()

    logger.info("\nAfter rollback:")
    logger.info("  Products: %s (should be 0, not 3)", final_product_count)
    logger.info("  Reviews: %s (should be 0, not 2)", final_review_count)

    assert (
        final_product_count == 0
    ), "No products should exist after rollback (all 3 undone)"
    assert (
        final_review_count == 0
    ), "No reviews should exist after rollback (all 2 undone)"
    logger.info("\n[OK] Atomic: all writes rolled back together, none left behind")
