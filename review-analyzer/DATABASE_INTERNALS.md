# Database Internals: Engine, Session, Connection Pool Explained

## Real-World Analogy: Bank Teller Window

Think of your database like a bank:

```
┌─────────────────────────────────────────────────────┐
│                    BANK BUILDING                    │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  PostgreSQL Database Server                 │   │
│  │  (The actual bank vault with all data)     │   │
│  └─────────────────────────────────────────────┘   │
│                      ↑                              │
│            DATABASE CONNECTIONS                    │
│            (Wires to the vault)                    │
│                      │                              │
│  ┌───────┬───────┬───────┬───────┐                │
│  │Teller │Teller │Teller │Teller │  (Pool of 5) │
│  │  #1   │  #2   │  #3   │  #4   │               │
│  └───────┴───────┴───────┴───────┘                │
│                      ↑                              │
│         CONNECTION POOL (Managed by Engine)       │
│                      │                              │
│  ┌───────┬───────┬───────┐                        │
│  │Request│Request│Request│  Your applications   │
│  │  A    │  B    │  C    │  (Customers in line) │
│  └───────┴───────┴───────┘                        │
└─────────────────────────────────────────────────────┘
```

---

## The Three Layers

### Layer 1: ENGINE (Connection Pool Manager)
**What it is:** The bank manager who controls the tellers (connections)

```python
engine = create_engine(
    "postgresql://user:password@localhost:5432/review_db",
    echo=True,
    pool_size=5,        # Keep 5 connections ready
    max_overflow=10     # Allow 10 more if needed
)
```

**What the engine does:**
- Creates a pool of 5 database connections (like 5 teller windows)
- Keeps them running 24/7, ready to use
- Gives connections to requests when they need them
- Takes connections back when requests finish
- Recycles connections for the next request

**Why not just create one connection?**
```
❌ One connection at a time:
   Request A: "Get connection" → 5 seconds waiting
   Request B: "Get connection" → 5 seconds waiting (A is using it)
   Request C: "Get connection" → 10 seconds waiting
   
✅ Pool of 5 connections:
   Request A: Gets connection 1 immediately
   Request B: Gets connection 2 immediately
   Request C: Gets connection 3 immediately
   All run in parallel!
```

**Engine is long-lived:**
```python
# In database.py
engine = create_engine(...)  # Created ONCE when app starts
# Reused for ALL requests (it's global)
```

---

### Layer 2: SESSION (Transaction Manager)
**What it is:** A transaction - like one customer's visit to the bank

```python
db = SessionLocal()  # Start a new transaction
# Now you can do:
db.query(Product).all()      # Read from database
db.add(new_product)          # Add to database
db.commit()                  # Save changes
db.close()                   # End transaction
```

**Key concepts:**

#### A. Identity Map (Session tracks objects)
```python
logger = logging.getLogger(__name__)

# First query
product1 = db.query(Product).get(1)
logger.info("%s", product1.name)  # "Laptop"

# Same query again
product2 = db.query(Product).get(1)
logger.info("%s", product2 is product1)  # True! Not a new object
# ↑ Session remembers it already loaded this

# Change it
product1.name = "Gaming Laptop"
logger.info("%s", product2.name)  # "Gaming Laptop" 
# ↑ Both variables point to same object in memory
```

#### B. Lazy Loading (Load on demand)
```python
logger = logging.getLogger(__name__)

# Session loads only what you ask for
product = db.query(Product).get(1)
# At this point: Product #1 is loaded
logger.info("%s", product.name)  # "Laptop"

# But reviews aren't loaded yet!
# Only when you access them:
for review in product.reviews:  # NOW it queries reviews table
    logger.info("%s", review.text)
```

#### C. Change Tracking
```python
product = db.query(Product).get(1)
product.name = "New Name"
# Session sees: "Hey, this object changed!"

db.commit()
# Session generates: UPDATE products SET name='New Name' WHERE id=1
# Sends only the changed fields to database
```

---

### Layer 3: CONNECTION (Network Wire)
**What it is:** The actual network connection to PostgreSQL

```python
# Inside the session:
connection = engine.raw_connection()  
# This is what you're NOT seeing
# But SQLAlchemy manages it behind the scenes

# When you do:
db.query(Product).all()
# Behind the scenes:
# 1. Gets a connection from the pool
# 2. Sends SQL: "SELECT * FROM products"
# 3. Receives rows from PostgreSQL
# 4. Returns connection to pool
# 5. Gives you Python objects
```

---

## How They Work Together: A Real Request

### Code You Write:
```python
@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    return products
```

### What Actually Happens (Step-by-Step):

#### Step 1: Engine Created (App Start - Once)
```python
engine = create_engine("postgresql://...")
# ✓ Pool created: 5 connections standing by
# ✓ Ready to accept requests
```

#### Step 2: Request Arrives
```
User: GET /products
FastAPI: "I need a database session!"
FastAPI: Calls get_db()
```

#### Step 3: get_db() Runs
```python
def get_db():
    db = SessionLocal()  # SessionLocal uses engine
    try:
        yield db
    finally:
        db.close()
```

**What `SessionLocal()` does:**
```python
SessionLocal = sessionmaker(bind=engine)
# When you call SessionLocal():
# 1. Gets a connection from engine's pool
#    (If no connection available, waits or creates new one)
# 2. Creates a Session wrapper around that connection
# 3. Returns the Session
```

**Result:** A brand new Session object, connected to database via engine's pool

#### Step 4: Route Executes
```python
def list_products(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    #         ↑ Using the Session from get_db()
    
    # Under the hood:
    # 1. db.query() creates a query builder
    # 2. .all() executes it
    # 3. Gets a connection from pool (via engine)
    # 4. Sends: SELECT id, name, price, rating FROM products
    # 5. Receives rows from PostgreSQL
    # 6. Converts each row to ProductModel Python object
    # 7. Returns list of objects
    
    return products
```

#### Step 5: Request Finishes
```python
# Route returns, response is sent to user
# Now finally block in get_db() runs:

finally:
    db.close()  # Session.close() does:
    # 1. Closes the transaction
    # 2. Returns connection back to engine's pool
    # 3. Clears all objects from session
```

**Result:** Connection is ready for next request

---

## Visual Timeline of One Request

```
Time →
┌──────────────────────────────────────────────────────────────┐
│ App Startup                                                  │
│ engine = create_engine(...)                                  │
│ └─ Pool: [Conn1, Conn2, Conn3, Conn4, Conn5] (all idle)    │
└──────────────────────────────────────────────────────────────┘
                            ↓
                        (Time passes)
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Request A arrives: GET /products                             │
├──────────────────────────────────────────────────────────────┤
│ get_db() called                                              │
│ └─ db = SessionLocal()                                       │
│    └─ Grabs Conn1 from pool                                  │
│       Pool now: [Conn2, Conn3, Conn4, Conn5] (Conn1 busy)   │
│                                                              │
│ Route executes:                                              │
│ products = db.query(...).all()                               │
│ └─ Uses Conn1 to query PostgreSQL                            │
│    "SELECT * FROM products"                                  │
│    Receives 100 rows, converts to objects                    │
│                                                              │
│ Return response to user                                      │
│                                                              │
│ db.close()                                                   │
│ └─ Returns Conn1 to pool                                     │
│    Pool now: [Conn1, Conn2, Conn3, Conn4, Conn5] (all idle) │
└──────────────────────────────────────────────────────────────┘
```

---

## Engine Properties (Advanced)

```python
engine = create_engine(
    DATABASE_URL,
    echo=True,           # Print all SQL queries (debugging)
    pool_size=5,         # Number of connections to keep ready
    max_overflow=10,     # Extra connections if pool exhausted
    pool_recycle=3600,   # Recycle connections every hour
    pool_pre_ping=True   # Test connection before using (prevents "connection lost" errors)
)
```

**What each does:**

### `echo=True`
```
When you do: db.query(Product).all()

Console prints:
BEGIN (implicit)
SELECT id, name, price, rating FROM products
... (rows returned)
COMMIT

Perfect for debugging!
```

### `pool_size=5, max_overflow=10`
```
Normal situation (5 requests):
Pool: [C1, C2, C3, C4, C5] all in use
New request arrives: Gets one back when done

High load (18 requests):
Pool: [C1, C2, C3, C4, C5] (fixed pool)
Extra: [C6, C7, C8, ... C15] (overflow connections)
Total available: 15 connections (5 + 10)

Over limit (20 requests):
Request waits in line until a connection is freed
```

### `pool_recycle=3600`
```
Some databases close idle connections after 30 minutes
If your app sits idle, then makes a request:
❌ "Connection lost" error

Solution: Recycle connections every hour
✅ Old connections thrown away
✅ New fresh connections created
```

### `pool_pre_ping=True`
```
Before giving you a connection, SQLAlchemy tests it:
engine: "Hey Conn1, are you alive?"
Conn1: (responds)
engine: "Great! Here you go"

If Conn1 is dead:
engine: "Conn1 is dead, creating new one"
```

---

## Session vs Engine: Key Differences

| Aspect | Engine | Session |
|--------|--------|---------|
| **Lifetime** | App startup → shutdown (long-lived) | Per request (short-lived) |
| **Quantity** | ONE per app | MANY (one per request) |
| **Purpose** | Manages connection pool | Manages one transaction |
| **Created** | `create_engine()` once | `SessionLocal()` per request |
| **Cleanup** | Closed when app stops | Closed after each request |
| **Memory** | Constant | Cleaned up per request |

---

## Common Mistakes

### ❌ Mistake 1: Creating engine per request
```python
@router.get("/products")
def list_products():
    engine = create_engine(DATABASE_URL)  # ❌ WRONG!
    # Creates new engine every single request
    # Connection pool wasted
    # Performance disaster
```

**✅ Correct:**
```python
# database.py (top level, created once)
engine = create_engine(DATABASE_URL)

# In route
@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    # Uses existing engine via SessionLocal
```

### ❌ Mistake 2: Not closing session
```python
@router.get("/products")
def list_products():
    db = SessionLocal()
    products = db.query(Product).all()
    return products
    # ❌ db.close() never called!
    # Connection leaks, runs out eventually
```

**✅ Correct:**
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # Always called, even if error
```

### ❌ Mistake 3: Sharing session across requests
```python
global_session = SessionLocal()  # ❌ WRONG!

@router.get("/products")
def list_products():
    return global_session.query(Product).all()

@router.post("/products")
def create_product(product: Product):
    global_session.add(product)
    global_session.commit()
    # Request A reading while Request B writing = CORRUPTION
```

**✅ Correct:**
```python
# Each request gets its own session
@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@router.post("/products")
def create_product(product: Product, db: Session = Depends(get_db)):
    db.add(product)
    db.commit()
```

---

## Memory/Resource Flow

```
App Startup:
┌──────────────────────┐
│  engine created      │
│  ├─ Allocates 5 TCP  │
│  │  connections      │
│  └─ RAM: ~10-20MB    │
└──────────────────────┘

Request 1 arrives:
┌──────────────────────┐
│  SessionLocal()      │
│  ├─ Grabs Conn1      │
│  ├─ Creates Session  │
│  └─ RAM: ~1-2MB      │
└──────────────────────┘
  (runs query)
        ↓
┌──────────────────────┐
│  db.close()          │
│  ├─ Returns Conn1    │
│  ├─ Clears objects   │
│  └─ RAM freed        │
└──────────────────────┘

Request 2 arrives:
┌──────────────────────┐
│  SessionLocal()      │
│  ├─ Grabs Conn1      │ (reused!)
│  ├─ Creates Session  │
│  └─ RAM: ~1-2MB      │
└──────────────────────┘

Result: 
- Engine uses constant memory (pool of connections)
- Sessions are garbage collected after each request
- No memory leaks!
```

---

## Summary: What Each Component Does

| Component | Job | Analogy |
|---|---|---|
| **Engine** | Manages pool of database connections | Bank manager with 5 teller windows |
| **SessionLocal** | Factory that creates sessions | Line at bank requesting a teller |
| **Session** | Represents one transaction/request | One customer's transaction at one teller |
| **Connection** | Actual network wire to PostgreSQL | The teller's desk (communication channel) |
| **Pool** | Collection of reusable connections | The 5 teller windows |

When you use `db: Session = Depends(get_db)`:
1. FastAPI calls `get_db()`
2. `get_db()` calls `SessionLocal()`
3. `SessionLocal()` gets a connection from engine's pool
4. Wraps it in a Session object
5. Yields to your route
6. Route uses the session to query
7. Route returns, finally block closes session
8. Connection returned to pool for reuse
9. Next request reuses that connection
