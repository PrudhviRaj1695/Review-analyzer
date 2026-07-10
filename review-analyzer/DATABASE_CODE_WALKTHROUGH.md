# Database Code Walkthrough: Step-by-Step

This document shows exactly what happens in our database code, line by line.

---

## File 1: database.py (The Setup)

```python
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()  # ← Loads .env file into environment variables

DATABASE_URL = os.getenv("DATABASE_URL")
# Reads from .env file:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/review_db
```

### Step 1: Create Engine
```python
engine = create_engine(
    DATABASE_URL,
    echo=True  # Print SQL queries for debugging
)
```

**What happens:**
```
1. SQLAlchemy connects to postgresql://...
2. Creates connection pool
3. Opens 5 connections to PostgreSQL server
4. Keeps them ready in memory

Result: 'engine' object ready to be used
        It manages the pool for the entire app lifetime
```

### Step 2: Create SessionLocal Factory
```python
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit after each query
    autoflush=False,   # Don't auto-flush changes before query
    bind=engine        # Use our engine for connections
)
```

**What is SessionLocal?**
```python
# It's a factory function
# Every time you call it, it creates a new Session:

session1 = SessionLocal()  # New session 1
session2 = SessionLocal()  # New session 2
session3 = SessionLocal()  # New session 3

# Each gets a connection from engine's pool
```

### Step 3: Create get_db Dependency Function
```python
def get_db() -> Session:
    db = SessionLocal()  # Create new session from pool
    try:
        yield db  # Pause, give session to route
    finally:
        db.close()  # Resume, close session after route
```

**Execution timeline:**

```
Time 0: get_db() called
        ├─ db = SessionLocal()
        │  └─ Grabs a connection from engine's pool
        ├─ try: (enter)
        └─ yield db (PAUSE HERE)

Time 1-5: Route function executes
        ├─ products = db.query(...).all()
        │  └─ Uses the yielded session
        ├─ ... do more stuff ...
        └─ return response

Time 6: Route finished, execution resumes after yield
        ├─ finally: (enter)
        ├─ db.close()
        │  └─ Returns connection to pool
        │  └─ Clears session memory
        └─ get_db() ends
```

---

## File 2: products.py (The Route)

### Original Code (Without Database)
```python
@router.get("")
def list_products():
    # Returns in-memory list (no database)
    return [
        ProductOut(...) 
        for product in products  # ← in-memory list
    ]
```

**Problem:** Data lost when app restarts

---

### New Code (With Database)
```python
@router.get("")
def list_products(db: Session = Depends(get_db)):
    # db parameter comes from get_db() dependency
    
    db_products = db.query(ProductModel).all()
    # ↑ Query the actual database
    
    return [
        ProductOut(
            id=product.id,
            Product_name=product.name,
            ...
        )
        for product in db_products
    ]
```

**What `db.query(ProductModel).all()` does:**

```
1. db.query(ProductModel)
   └─ Creates a query builder, targets ProductModel

2. .all()
   └─ Executes the query
   
Under the hood:
   ├─ SQLAlchemy generates SQL:
   │  SELECT id, name, price, rating FROM products
   │
   ├─ Sends SQL through connection to PostgreSQL
   │
   ├─ PostgreSQL executes, returns rows
   │
   ├─ SQLAlchemy converts rows to Python objects:
   │  ProductModel(id=1, name='Laptop', price=999.99, ...)
   │  ProductModel(id=2, name='Mouse', price=29.99, ...)
   │
   └─ Returns list of ProductModel objects

Result: db_products = [ProductModel(...), ProductModel(...), ...]
```

---

## Flow Diagram: One Complete Request

### Request: User clicks "Get all products"

```
┌────────────────────────────────────────────────────┐
│ Browser sends: GET /products                       │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ FastAPI receives request                           │
│ Looks at route: def list_products(db: Session ...) │
│ Sees: db = Depends(get_db)                         │
│ "I need to inject get_db()"                        │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ FastAPI calls: get_db()                            │
│                                                    │
│ def get_db():                                      │
│     db = SessionLocal()                            │
│     # SessionLocal() calls engine.connect()        │
│     # Engine gets Conn#1 from pool                 │
│     # Creates Session wrapping Conn#1             │
│     try:                                           │
│         yield db  ← Returns here                   │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ FastAPI injects: list_products(db=<Session obj>)   │
│                                                    │
│ def list_products(db: Session = Depends(get_db)): │
│     # db is now the session yielded from get_db   │
│                                                    │
│     db_products = db.query(ProductModel).all()     │
│     # ├─ query() sends SQL to PostgreSQL          │
│     # ├─ via Conn#1 (from the session)            │
│     # ├─ SELECT id,name,price,rating FROM products │
│     # ├─ PostgreSQL returns 3 rows                │
│     # └─ SQLAlchemy converts to ProductModel      │
│     #    objects                                  │
│     # Result: [ProductModel(...), ...]            │
│                                                    │
│     return [ProductOut(...), ...]                 │
│     # FastAPI converts to JSON                    │
│     # Returns response                            │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ get_db() finishes:                                 │
│     finally:                                       │
│         db.close()                                 │
│         # ├─ Closes transaction                   │
│         # ├─ Returns Conn#1 to engine's pool      │
│         # └─ Clears session objects               │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ Browser receives JSON response:                    │
│ [                                                  │
│   {"id": 1, "Product_name": "Laptop", ...},       │
│   {"id": 2, "Product_name": "Mouse", ...},        │
│   {"id": 3, "Product_name": "Keyboard", ...}      │
│ ]                                                  │
└────────────────────────────────────────────────────┘
```

---

## Multiple Concurrent Requests

### Scenario: 3 users request GET /products at the same time

```
t=0ms  User A clicks        User B clicks        User C clicks
       GET /products        GET /products        GET /products
            ↓                    ↓                    ↓
       get_db() A-1         get_db() B-1         get_db() C-1
       │                    │                    │
       SessionLocal()       SessionLocal()       SessionLocal()
       │                    │                    │
       Grabs Conn#1         Grabs Conn#2         Grabs Conn#3
       ↓                    ↓                    ↓

t=5ms  list_products()      list_products()      list_products()
       │                    │                    │
       db.query(...)        db.query(...)        db.query(...)
       with Conn#1          with Conn#2          with Conn#3
       ↓                    ↓                    ↓

t=10ms PostgreSQL executes  PostgreSQL executes  PostgreSQL executes
       3 parallel queries   3 parallel queries   3 parallel queries
       ↓                    ↓                    ↓

t=15ms Return results       Return results       Return results
       ↓                    ↓                    ↓
       finally:            finally:             finally:
       db.close()          db.close()           db.close()
       Returns Conn#1      Returns Conn#2       Returns Conn#3
       ↓                    ↓                    ↓

t=20ms Response to User A   Response to User B   Response to User C

Result: All 3 users get data in parallel!
        No waiting for each other
        Each request isolated in its own session
        Connections reused from pool
```

---

## What Happens Inside Each Part

### Inside `SessionLocal()`:

```python
SessionLocal()
    ↓
sessionmaker.__call__()  # Call the factory
    ↓
request_connection_from_pool()  # From engine
    ↓
engine.pool.get_connection()
    ├─ Check pool: [Conn1, Conn2, ...]
    ├─ Pool has available connections? → Yes, return Conn#X
    └─ Pool empty? → Create new connection
    ↓
Session(connection=Conn#X)  # Wrap in Session
    ↓
return Session object
```

### Inside `db.query(ProductModel).all()`:

```python
db.query(ProductModel)
    ↓
Query object created
    ├─ Model: ProductModel
    ├─ Connected to: db (Session)
    └─ Not executed yet
    ↓
.all()
    ↓
Execute the query
    ├─ Build SQL: SELECT id, name, price, rating FROM products
    │
    ├─ Get connection from session
    │  cursor = session.connection().cursor()
    │
    ├─ Send SQL through connection:
    │  cursor.execute("SELECT ...")
    │
    ├─ PostgreSQL processes
    │  └─ Looks in table "products"
    │  └─ Returns rows: (1, 'Laptop', 999.99, 4.5), (2, 'Mouse', ...
    │
    ├─ SQLAlchemy receives rows
    │
    ├─ Convert each row to ProductModel:
    │  for row in rows:
    │      obj = ProductModel(
    │          id=row[0],      # 1
    │          name=row[1],    # 'Laptop'
    │          price=row[2],   # 999.99
    │          rating=row[3]   # 4.5
    │      )
    │      objects.append(obj)
    │
    └─ return [ProductModel(...), ProductModel(...), ...]
```

### Inside `db.close()`:

```python
db.close()
    ↓
Flush any pending changes (if exists)
    ├─ Any .add() not yet saved? → Execute INSERT/UPDATE/DELETE
    └─ Commit or rollback based on state
    ↓
Close the connection
    ├─ connection.close()
    └─ Connection goes back to engine's pool
    ↓
Clear session cache
    ├─ db.expunge_all()  # Forget all loaded objects
    └─ Memory freed
    ↓
Return to pool [Conn1, Conn2, Conn3, Conn4, Conn5]
```

---

## Memory State During Request

### Startup:
```
Engine: <SQLAlchemy Engine>
  ├─ Pool: [Conn1-idle, Conn2-idle, Conn3-idle, Conn4-idle, Conn5-idle]
  └─ Memory: ~15MB
```

### Request arrives, get_db() called:
```
Engine: <SQLAlchemy Engine>
  ├─ Pool: [Conn2-idle, Conn3-idle, Conn4-idle, Conn5-idle]
  │        (Conn1 taken by request)
  └─ Memory: ~15MB (same, just redistributed)

Session A: <SQLAlchemy Session>
  ├─ Connection: Conn1
  ├─ Identity Map: {} (empty, nothing loaded yet)
  └─ Memory: ~1MB
```

### Query executed:
```
Engine: Same
  └─ Memory: ~15MB

Session A: <SQLAlchemy Session>
  ├─ Connection: Conn1
  ├─ Identity Map: {
  │    1: ProductModel(id=1, name='Laptop', ...),
  │    2: ProductModel(id=2, name='Mouse', ...),
  │    3: ProductModel(id=3, name='Keyboard', ...)
  │  }
  └─ Memory: ~2-3MB (objects in memory)
```

### Request finishes, db.close():
```
Engine: <SQLAlchemy Engine>
  ├─ Pool: [Conn1-idle, Conn2-idle, Conn3-idle, Conn4-idle, Conn5-idle]
  │        (Conn1 returned)
  └─ Memory: ~15MB (same)

Session A: Deleted
  └─ Memory: Freed (~2-3MB reclaimed)

Result: System ready for next request
```

---

## Summary Checklist

✅ **Engine**: One per app, manages connection pool
✅ **Session**: Many (one per request), manages transaction  
✅ **Pool**: Reuses connections for efficiency
✅ **yield**: Pauses function, lets route execute, resumes for cleanup
✅ **Depends()**: FastAPI dependency injection mechanism
✅ **db.close()**: Always called (via finally) to cleanup
✅ **No sharing**: Each request gets its own session (isolation)
✅ **No leaks**: Connections always returned to pool

This is why FastAPI + SQLAlchemy is so powerful:
- Fast (connection pooling)
- Safe (isolation via sessions)
- Scalable (handles concurrent requests)
- Clean (automatic dependency injection)
