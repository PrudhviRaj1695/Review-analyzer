import sys
from pathlib import Path
import pytest

# Add the project root to Python path so 'app' module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path is set
from app.routers import products as products_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_products():
    """
    Auto-use fixture that resets products list before and after each test.
    This ensures test isolation - no state leaks between tests.
    """
    # ARRANGE - Clean state before test
    products_module.products = []

    # ACT - Test runs here
    yield

    # CLEANUP - Clean state after test
    products_module.products = []
