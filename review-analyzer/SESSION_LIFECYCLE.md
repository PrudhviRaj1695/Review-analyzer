# Database Session Lifecycle Per Request

## The Flow: What Happens When a Request Comes In

```
┌─────────────────────────────────────────────────────────────────┐
│ User makes HTTP request: GET /products                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI receives request                                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI sees: db: Session = Depends(get_db)                    │
│ → FastAPI calls get_db() function                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ get_db() STARTS (enters function)                               │
│                                                                 │
│   db = SessionLocal()  ← Creates new database session          │
│                          Connected to PostgreSQL               │
│   try:                                                          │
│       yield db  ← Returns session to route function            │
│                  (execution pauses here)                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Route function EXECUTES with the session:                       │
│                                                                 │
│   def list_products(db: Session = Depends(get_db)):            │
│       db_products = db.query(ProductModel).all()               │
│       # ↑ Using the session to query database                 │
│       return [...]                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Route finishes, returns response to user                        │
│ Execution resumes in get_db() after yield                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ get_db() CLEANUP (finally block)                                │
│                                                                 │
│   finally:                                                      │
│       db.close()  ← Closes database connection                │
│                    Returns connection back to pool             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Response sent to user                                           │
│ Session is cleaned up                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why `yield` Instead of `return`?

### Without yield (BROKEN):
```python
def get_db():
    db = SessionLocal()
    return db
    # ❌ No cleanup! Connection stays open forever
    # ❌ Connection leaks, database runs out of connections
```

### With yield (CORRECT):
```python
def get_db():
    db = SessionLocal()
    try:
        yield db     # Pause, give session to route
                     # Route runs here while paused
    finally:
        db.close()   # Resume after route finishes, cleanup
```

The `yield` is like a **pause button**: it gives the session to the route, waits for the route to finish, then resumes to clean up.

---

## Session Lifecycle Diagram

```
Request 1                    Request 2                  Request 3
   │                            │                          │
   ├─ get_db()                  ├─ get_db()                ├─ get_db()
   │  └─ Session #1 created     │  └─ Session #2 created   │  └─ Session #3 created
   │
   ├─ list_products()           ├─ list_products()         ├─ list_products()
   │  └─ Query DB               │  └─ Query DB             │  └─ Query DB
   │     (Session #1 active)    │     (Session #2 active)  │     (Session #3 active)
   │
   ├─ Response sent             ├─ Response sent           ├─ Response sent
   │
   └─ db.close()                └─ db.close()              └─ db.close()
      └─ Session #1 closed         └─ Session #2 closed        └─ Session #3 closed
```

Each request gets its **own isolated session**:
- Request 1 can't interfere with Request 2
- Each session handles its own database connection
- All connections are properly closed (no leaks)

---

## Code Flow: The Key Parts

### 1. Engine (Connection Pool)
```python
engine = create_engine(DATABASE_URL)
# ↑ Creates a pool of 5-10 database connections ready to use
# Engine reuses connections across requests
```

### 2. SessionLocal Factory
```python
SessionLocal = sessionmaker(bind=engine)
# ↑ Factory that creates new Session objects
# Each call: SessionLocal() → new Session from the pool
```

### 3. get_db Dependency
```python
def get_db():
    db = SessionLocal()      # Get session from pool
    try:
        yield db             # Give to route
    finally:
        db.close()           # Return to pool
```

### 4. Route Using Dependency
```python
@router.get("")
def list_products(db: Session = Depends(get_db)):
    # FastAPI automatically calls get_db()
    # Passes returned session as 'db' parameter
    products = db.query(ProductModel).all()
    return products
    # When route finishes, finally block runs (cleanup)
```

---

## Per-Request Session Lifecycle Summary

| Phase | What Happens | Code Location |
|-------|---|---|
| **1. Request arrives** | User makes GET /products | HTTP client |
| **2. Dependency injection** | FastAPI sees `Depends(get_db)` | FastAPI routing |
| **3. get_db() starts** | Session created from pool | `db = SessionLocal()` |
| **4. Yield** | Session given to route | `yield db` (paused) |
| **5. Route executes** | Uses session to query database | `db.query(...)` |
| **6. Route returns** | Response prepared | `return [...]` |
| **7. Cleanup** | Finally block executes | `db.close()` |
| **8. Session returned** | Connection back to pool | Connection pool |
| **9. Response sent** | User gets response | HTTP response |

---

## Why This Pattern Is Important

✅ **Resource Management**: Sessions are always closed (no connection leaks)
✅ **Isolation**: Each request gets its own session (no cross-request interference)
✅ **Scalability**: Connection pooling lets many concurrent requests share connections
✅ **Error Safety**: `finally` block runs even if route crashes (cleanup guaranteed)
✅ **Clean Code**: No need to manually pass session around, FastAPI injects it

---

## Real World Example

```python
# Two concurrent requests at the same time

Request A: GET /products
├─ get_db() creates Session A
├─ list_products(db=Session A)
│  └─ db.query(ProductModel).all()
│     └─ "SELECT * FROM products" executes
└─ db.close() returns Session A to pool

Request B: GET /products
├─ get_db() creates Session B
├─ list_products(db=Session B)
│  └─ db.query(ProductModel).all()
│     └─ "SELECT * FROM products" executes
└─ db.close() returns Session B to pool

Both requests:
- Use different sessions
- Don't interfere with each other
- Properly clean up after themselves
```
