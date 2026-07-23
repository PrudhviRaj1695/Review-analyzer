"""Pytest configuration and fixtures for database testing."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Base

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Use SQLite in-memory database for testing
# StaticPool keeps the in-memory database alive for the entire session
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


# Enable foreign key constraints in SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraint enforcement in SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Create test database schema once per test session.

    This runs once at the start of all tests and creates the tables.
    The StaticPool ensures the in-memory database persists for all tests.
    """
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup: drop all tables after all tests complete
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db():
    """
    Provide a test database session for a single test.

    What happens:
    1. SETUP: Clear all data from tables
    2. TEST: Test runs with clean, empty database
    3. CLEANUP: Clear all data again

    The tables already exist (created in setup_test_db), we just clear them
    to ensure isolation between tests.
    """
    # Clear all data from tables before test (using SQLAlchemy 2.0 API)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    # Create a new session for this test
    session = TestingSessionLocal()

    # Override FastAPI's get_db() to use test session
    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Cleanup: close session and clear tables
    session.close()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    # Clear dependency overrides for next test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(db: Session):
    """
    Provide a TestClient with test database.

    The db fixture automatically configures dependency overrides to use
    the test database. This fixture creates the client that will use it.
    """
    return TestClient(app)
