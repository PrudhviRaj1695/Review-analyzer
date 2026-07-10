# Database Transactions Explained: All-or-Nothing Guarantee

## What is a Transaction?

A **transaction** is a unit of work that either **completely succeeds or completely fails** — no partial results.

Think of it like transferring money between bank accounts:
- Debit $100 from Account A
- Credit $100 to Account B

**Either BOTH happen, or NEITHER happens.** You never want Account A debited but Account B not credited (money vanishes!).

---

## The Two Tests: Rollback vs Commit

### Test 1: Rollback on Error (No Partial Data)

```python
def test_transaction_rollback_on_error(db):
    """Force error mid-transaction - nothing gets written."""
    
    try:
        # Step 1: Create product
        product = Product(id=1, name="Test", price=99.99)
        db.add(product)
        db.flush()  # Write to transaction buffer
        
        # At this point: product exists in memory/transaction, NOT in database
        assert db.query(Product).count() == 1  # ← Visible within transaction
        
        # Step 2: Force error BEFORE commit
        raise RuntimeError("Intentional error!")
        
    except RuntimeError:
        # Error! Rollback entire transaction
        db.rollback()
    
    # ASSERT: Product was NOT written to database
    assert db.query(Product).count() == 0  # ✅ No partial data!
```

**What happened:**

```
Time →
│
├─ db.add(product)
│  └─ Added to transaction buffer
│
├─ db.flush()
│  └─ Visible within this transaction
│  └─ NOT committed to database yet
│
├─ raise RuntimeError()
│  └─ Error occurs!
│
├─ db.rollback()
│  └─ ENTIRE transaction discarded
│  └─ Product never written to database
│
└─ Result: Database unchanged (ALL-OR-NOTHING)
```

**Result:** ✅ NO data was written — transaction rolled back completely

---

### Test 2: Successful Commit (All Data Written)

```python
def test_successful_transaction_commits_all_data(db):
    """Successful operations - all data is written."""
    
    # Step 1: Create and commit product
    product = Product(id=1, name="Laptop", price=999.99)
    db.add(product)
    db.commit()  # ← Explicitly commit
    
    # Step 2: Create and commit review
    review = Review(product_id=1, text="Excellent!")
    db.add(review)
    db.commit()  # ← Explicitly commit
    
    # ASSERT: All data was written
    assert db.query(Product).count() == 1  # ✅ Product exists
    assert db.query(Review).count() == 1   # ✅ Review exists
```

**What happened:**

```
Time →
│
├─ db.add(product)
├─ db.commit()
│  └─ Product written to database
│  └─ Transaction ends
│
├─ db.add(review)
├─ db.commit()
│  └─ Review written to database
│  └─ Transaction ends
│
└─ Result: Both rows in database (ALL operations succeeded)
```

**Result:** ✅ ALL data was written — both commits succeeded

---

## Transaction Guarantees: ACID Properties

Databases guarantee transactions follow **ACID**:

### A = Atomicity (All-or-Nothing)
```python
try:
    db.add(product)
    db.add(review)
    db.commit()  # Both succeed
except Exception:
    db.rollback()  # Both fail, nothing is written
```

**Guarantee:** Transaction succeeds completely or fails completely. No partial writes.

**Example:**
```
❌ BAD (without ACID):
├─ Product written ✓
├─ Error!
└─ Review NOT written ✗
   → Orphaned product exists!

✅ GOOD (with ACID):
├─ Product added to transaction
├─ Review added to transaction
├─ Error!
└─ Both rollback → database unchanged
```

---

### C = Consistency (Valid State to Valid State)
```python
# Before transaction: Database has 2 products, 5 reviews
# Transaction adds: 1 product, 3 reviews

# During transaction: Partially applied? NO - hidden
# After commit: Database has 3 products, 8 reviews
# After rollback: Database still has 2 products, 5 reviews
```

**Guarantee:** Database goes from one valid state to another valid state. Never left in inconsistent state.

**Our example:**
- Valid state: All reviews have valid product_id (FK constraint)
- Transaction: Add product + review (both together)
- If error: Rollback keeps valid state (no orphan reviews)

---

### I = Isolation (Concurrent Operations Don't Interfere)
```python
# Request A creates product
# Request B reads products

# ISOLATED: Request B either sees:
#   - Product (if A committed)
#   - No product (if A hasn't committed)
#   - NOT "partially written" product

Request A: db.add(product); db.commit()
Request B: db.query(Product).all()  # Sees committed product
```

**Guarantee:** Transactions don't see partial writes from other transactions.

---

### D = Durability (Committed Data Persists)
```python
db.add(product)
db.commit()  # ← Data now on disk

# Even if server crashes immediately after,
# the product is safe on disk
# It won't disappear
```

**Guarantee:** Once committed, data persists even through crashes.

---

## Commit Boundaries: When Does Data Get Written?

### Explicit Commit
```python
db.add(product)
# ← Product NOT in database yet

db.commit()
# ← Product NOW in database
# Transaction complete
```

### Implicit Rollback on Error
```python
try:
    db.add(product)
    raise Exception()
    db.commit()  # Never reached
except Exception:
    db.rollback()  # Undo everything
```

### Flush vs Commit
```python
db.add(product)

# FLUSH: Write to transaction buffer (invisible to other requests)
db.flush()
assert db.query(Product).count() == 1  # Visible within this transaction

# COMMIT: Write to disk (visible to other requests)
db.commit()
assert db.query(Product).count() == 1  # Visible to everyone
```

**Timeline:**
```
Memory    → Flush Buffer → Database
(Python)    (Transaction)   (Disk/Others)

db.add()    ✓ (Python memory)
            ✗ (not in transaction buffer yet)
            ✗ (not on disk)

db.flush()  ✓ (Python memory)
            ✓ (transaction buffer - visible within transaction)
            ✗ (not on disk/visible to others)

db.commit() ✓ (Python memory)
            ✓ (transaction buffer)
            ✓ (on disk - visible to everyone)
```

---

## Real-World Scenario: Preventing Orphan Reviews

Our application creates products and reviews. Without transactions:

### ❌ Without Transactions (Vulnerable)
```python
def create_product_with_review(product_data, review_data):
    # Create product
    product = Product(**product_data)
    db.add(product)
    db.commit()  # ← Committed, visible to other requests
    
    # Error happens here!
    if not validate_review(review_data):
        raise ValueError("Invalid review")
    
    # Create review
    review = Review(product_id=product.id, **review_data)
    db.add(review)
    db.commit()  # ← Might not reach here
    
# Result: Product exists without review (orphaned)!
```

**Problem:** Product committed before we knew if review was valid

### ✅ With Transactions (Safe)
```python
def create_product_with_review(product_data, review_data):
    try:
        # Both operations in ONE transaction
        product = Product(**product_data)
        db.add(product)
        
        # Validate AND add review in same transaction
        review = Review(product_id=product.id, **review_data)
        db.add(review)
        
        # Commit only if everything succeeds
        db.commit()
        
    except ValueError:
        # Any error → entire transaction rolls back
        db.rollback()
        raise
    
# Result: Either BOTH created, or NEITHER created
```

**Benefit:** All-or-nothing guarantee prevents orphaned products

---

## Test Output Explained

### Rollback Test
```python
def test_transaction_rollback_on_error(db):
    try:
        product = Product(id=1, ...)
        db.add(product)
        db.flush()
        
        # At this point: product in transaction buffer
        assert db.query(Product).count() == 1  # ← Visible here
        
        raise RuntimeError()  # ← BOOM!
        
    except RuntimeError:
        db.rollback()
    
    # After rollback: database unchanged
    assert db.query(Product).count() == 0  # ✅ Rollback worked!
```

**What this proves:**
- ✅ Flush makes data visible within transaction
- ✅ Error before commit prevents commit
- ✅ Rollback discards ALL changes
- ✅ No partial data written

---

## Common Patterns

### Pattern 1: Auto-Rollback on Error
```python
with db.begin():  # Context manager
    db.add(product)
    db.add(review)
    # If error: auto-rollback
    # If success: auto-commit
```

### Pattern 2: Explicit Control
```python
db.add(product)
try:
    db.commit()
except Exception:
    db.rollback()
    raise
```

### Pattern 3: Multiple Steps in One Transaction
```python
try:
    step1()  # Create product
    step2()  # Create review
    step3()  # Update stats
    db.commit()  # All succeed together
except Exception:
    db.rollback()  # All fail together
```

---

## Why This Matters for Your Application

### Without Transaction Control
```
POST /products/1/reviews
├─ Add review to database ✓
├─ Decrement product stock... ERROR!
└─ Review exists but stock NOT decremented
   → Inconsistent state!
```

### With Transaction Control
```
POST /products/1/reviews
├─ Add review (in transaction)
├─ Decrement stock (in transaction)
├─ Commit (all succeed)
   OR
├─ Error → Rollback (both undo)
└─ Database always consistent
```

---

## Commands for Manual Testing

### Start a transaction
```python
session = Session()
product = Product(name="Laptop", price=999)
session.add(product)
```

### Check what's in transaction (not committed)
```python
session.flush()  # Flush to buffer
session.query(Product).count()  # Visible in this transaction
```

### Commit (write to database)
```python
session.commit()  # Now visible to everyone
```

### Rollback (discard)
```python
session.rollback()  # Undo everything
```

---

## Summary: Transaction Guarantees

| Property | Guarantee | Example |
|---|---|---|
| **Atomicity** | All-or-nothing | Product + Review both succeed or both fail |
| **Consistency** | Valid state | No orphaned reviews (FK constraint holds) |
| **Isolation** | No interference | Other requests don't see partial writes |
| **Durability** | Persists | Committed data survives crashes |

**Key Takeaway:**
- `flush()` → visible in current transaction
- `commit()` → visible to everyone, persists
- `rollback()` → discard everything
- Errors before commit → automatic rollback → no partial data

The tests prove: **If anything fails, nothing is written. All-or-nothing guarantee.**
