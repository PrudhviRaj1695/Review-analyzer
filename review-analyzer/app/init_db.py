"""Initialize database tables from ORM models."""
from app.database import engine
from app.models import Base


def init_db():
    """Create all tables in the database based on ORM models.

    This reads the Base metadata (which contains all model definitions)
    and creates corresponding tables in PostgreSQL.

    Handles errors gracefully - if database connection fails (e.g., in tests),
    it's skipped since tests set up their own database.
    """
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables initialized")
    except Exception as e:
        # Fail silently - could be in test environment with different database
        print(f"⚠ Database initialization skipped: {type(e).__name__}")


if __name__ == "__main__":
    init_db()
