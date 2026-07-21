Hey Cortana, what is the weather still getting in Blackpool? Hey Cortana, turn off the light. Ing stop. # Transaction Rollback DemonstrationHey, Cortana. Stop speaking with his birthday alex

## What We Saw

Three tests demonstrate the **all-or-nothing guarantee** of database transactions:

### Test 1: Single Partial Write with Rollback

**Scenario:**
1. Add a product to the transaction ✓
2. Try to add a review referencing a non-existent product ✗
3. Foreign key constraint fails
4. Entire transaction rolls back

**Output:**
```
[OK] Product added to transaction (ID will be: 1)
     Within transaction: 1 product(s) exist
[ERROR] Error caught (as expected): IntegrityError
        Foreign key constraint violation
        Transaction rolled back

After rollback:
  Products: 0 (should be 0)
  Reviews: 0 (should be 0)
```

**Key Learning:** The product we added is NOT persisted because the transaction failed before commit. Zero data written.

---

### Test 2: Multi-Step Failure Rolls Back Everything

**Scenario:**
1. Add 3 products ✓
2. Add 2 reviews (valid) ✓
3. Try to add 3rd review with invalid product_id ✗
4. Foreign key constraint fails
5. **ALL 5 writes** are undone (not just the failed one)

**Output:**
```
[OK] Added Product 1 (ID: 1)
[OK] Added Product 2 (ID: 2)
[OK] Added Product 3 (ID: 3)
[OK] Added review for Product 1
[OK] Added review for Product 2
[FAIL] Attempting review with invalid product_id...
       IntegrityError raised as expected
       Entire transaction rolled back

After rollback:
  Products: 0 (should be 0, not 3)
  Reviews: 0 (should be 0, not 2)

[OK] Atomic: all writes rolled back together, none left behind
```

**Key Learning:** Rollback is transaction-wide. Even though 4 writes succeeded, all are undone because the 5th failed. This is **atomicity**.

---

### Test 3: Valid Transaction Commits Successfully

**Scenario:**
1. Add product ✓
2. Add review for that product ✓
3. Commit (all operations were valid)

**Output:**
```
[OK] Both operations valid
     Product ID: 1
     Review references product 1
     Transaction committed

After commit:
  Products: 1 (should be 1)
  Reviews: 1 (should be 1)
```

**Key Learning:** When all writes are valid, commit succeeds and data persists.

---

## What Transactions Guarantee: ACID Properties

Transactions provide four guarantees (ACID):

### 1. **Atomicity** (All-or-Nothing)
**What:** Either ALL writes in the transaction succeed and persist, OR none of them do.

**Proof:** Test 2 shows that when the 5th write fails, the earlier 4 are rolled back. The database never has 3 products + 2 reviews. It has either everything (0 after rollback) or nothing.

### 2. **Consistency**
**What:** The database maintains its integrity rules (like foreign key constraints).

**Proof:** We can't create a review for product_id=9999 when that product doesn't exist. The database rejects it.

### 3. **Isolation**
**What:** Concurrent transactions don't interfere with each other. Each sees a consistent snapshot.

**Note:** This demo doesn't show concurrent access, but SQLite enforces it automatically.

### 4. **Durability**
**What:** Once committed, data persists even if the system crashes.

**Note:** Our in-memory SQLite doesn't have disk durability, but a production database would.

---

## How It Works Under the Hood

### Transaction Lifecycle

```
1. BEGIN TRANSACTION (implicit when you start adding/modifying)
   └─ Database enters transaction mode
   
2. FLUSH (writes to database, but not yet permanent)
   └─ Changes are in the database, but not committed
   └─ If another session queries, it won't see uncommitted changes
   └─ If an error occurs here, nothing is lost yet
   
3a. COMMIT (success path)
   └─ All changes are permanent
   └─ Other sessions can now see the data
   
3b. ROLLBACK (error path)
   └─ All unflushed changes are discarded
   └─ Database returns to state before the transaction started
   └─ No partial data written
```

### Example from Test 1

```python
try:
    product = Product(name="Test Product", price=99.99, rating=4.5)
    db.add(product)
    db.flush()  # <- Changes are in the DB, but not committed
    #            Product exists in THIS transaction only
    
    # Now try to add invalid review
    bad_review = Review(product_id=9999, text="...")  # Invalid!
    db.add(bad_review)
    db.flush()  # <- This raises IntegrityError
    
    # Never reaches here

except IntegrityError:
    db.rollback()  # <- Undo everything since BEGIN
    # Product is gone, Review is gone
    # Database is clean
```

---

## Why This Matters

### Scenario: Bank Transfer

Without transactions:
```python
# Transfer $100 from Account A to Account B
account_a.balance -= 100  # $100 leaves A ✓
# System crashes here!
account_b.balance += 100  # $100 never arrives ✗
# Result: $100 disappears!
```

With transactions:
```python
try:
    account_a.balance -= 100
    db.flush()
    
    account_b.balance += 100
    db.flush()
    
    db.commit()  # Both changes are permanent
except:
    db.rollback()  # Both changes are undone
    # Result: Either both succeed or both fail. Money never disappears!
```

---

## Key Takeaways

| Concept | What It Means | How We Proved It |
|---------|---------------|-----------------|
| **Atomicity** | All-or-nothing | Partial writes rolled back in Test 2 |
| **No Partial Data** | Failed writes don't persist | Test 1: Product rolled back after error |
| **Transaction Boundary** | BEGIN ... COMMIT/ROLLBACK | Test 3: Valid commit persisted data |
| **Rollback Scope** | Transaction-wide undo | Test 2: All 5 operations undone together |

---

## In the Code

The magic happens in:
- [database.py](app/database.py) - Creates SessionLocal with `autocommit=False`
- [conftest.py](tests/conftest.py) - Enables foreign key constraints
- [test_transaction_rollback.py](tests/test_transaction_rollback.py) - Demonstrates all three scenarios

The key line in conftest:
```python
SessionLocal = sessionmaker(
    autocommit=False,  # <- This enables transaction mode
    autoflush=False,
    bind=engine
)
```

With `autocommit=False`, you control when changes become permanent:
```python
db.flush()    # Push to DB, but don't commit
db.commit()   # Make permanent (all-or-nothing)
db.rollback() # Undo all pending changes
```
