# Database Schema Design

## Entity Relationship Diagram (On Paper)

```
┌─────────────────────┐
│     products        │
├─────────────────────┤
│ id (PK)             │ ───┐
│ name                │    │
│ price               │    │ one-to-many
│ rating              │    │
└─────────────────────┘    │
                           │
                           │
                      ┌────▼──────────────────┐
                      │      reviews          │
                      ├───────────────────────┤
                      │ id (PK)               │
                      │ product_id (FK) ──────┘
                      │ text                  │
                      │ created_at            │
                      └───────────────────────┘
```

## Table Definitions

### products
| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Unique product identifier |
| name | VARCHAR(255) | NOT NULL | Product name |
| price | DECIMAL(10,2) | NOT NULL | Product price |
| rating | DECIMAL(3,2) | | Average rating (0.0-5.0) |

### reviews
| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Unique review identifier |
| product_id | INTEGER | FOREIGN KEY → products(id) | Reference to product |
| text | TEXT | NOT NULL | Review content |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Review creation time |

## Foreign Key Relationship

**Relationship Type:** One-to-Many
- One product can have many reviews
- Each review belongs to exactly one product

**FK Definition:**
```sql
FOREIGN KEY (product_id) REFERENCES products(id)
```

## What the FK Prevents: Orphan Reviews

### Without FK constraint (vulnerable):
```
products table:
id | name
1  | Laptop
2  | Mouse

reviews table:
id | product_id | text | created_at
1  | 1          | Great! | 2026-01-01
2  | 99         | Bad | 2026-01-02  ← ORPHAN! (product_id=99 doesn't exist)
3  | 3          | Good | 2026-01-03  ← ORPHAN! (product_id=3 doesn't exist)
```
❌ Problem: Reviews reference products that don't exist (data integrity violation)

### With FK constraint (protected):
```sql
FOREIGN KEY (product_id) REFERENCES products(id)
```

**Enforcement:**
1. **INSERT/UPDATE blocked:** Cannot insert/update a review with product_id that doesn't exist in products table
2. **DELETE cascading:** Can set `ON DELETE CASCADE` to automatically delete reviews when their product is deleted
3. **Data integrity:** Guarantees every review has a valid product

**Example:**
```sql
-- ❌ This INSERT will FAIL:
INSERT INTO reviews (product_id, text) VALUES (99, 'Bad');
-- Error: Foreign key constraint fails

-- ✅ This INSERT succeeds:
INSERT INTO reviews (product_id, text) VALUES (1, 'Great!');
-- product_id=1 exists in products table
```

## Additional Constraints

- **Cascade Delete:** `ON DELETE CASCADE` — when a product is deleted, all its reviews are automatically deleted
- **Cascade Update:** `ON UPDATE CASCADE` — if a product id changes (rare), review references update automatically
- **No NULL product_id:** Enforces every review must reference a product

