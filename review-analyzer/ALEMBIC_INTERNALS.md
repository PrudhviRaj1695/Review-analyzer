# How Alembic Works Internally: Step-by-Step

## The Core Idea

Alembic tracks **which migrations have been applied** using a special table in your database.

```
Database
├─ products table
├─ reviews table
└─ alembic_version table  ← The secret! Tracks migrations
```

---

## Before and After: The alembic_version Table

### BEFORE Running Any Migration

```
Database has NO alembic_version table
```

### AFTER Running First Migration

```sql
-- Alembic creates this table
CREATE TABLE alembic_version (
    version_num VARCHAR(32) PRIMARY KEY
);

-- After migration 520463b5e478 runs:
INSERT INTO alembic_version VALUES ('520463b5e478');

-- Result:
-- version_num
-- -----------
-- 520463b5e478
```

### AFTER Running Second Migration

```sql
-- After migration abc123def456 runs:
INSERT INTO alembic_version VALUES ('abc123def456');

-- Result:
-- version_num
-- -----------
-- 520463b5e478
-- abc123def456
```

Alembic reads this table to know what's been applied! 🔍

---

## Step-by-Step: How a Migration Gets Applied

### Our Migration File
**File:** `alembic/versions/520463b5e478_initial.py`

```python
revision = '520463b5e478'
down_revision = None

def upgrade():
    """Apply this migration."""
    op.create_table('products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    """Undo this migration."""
    op.drop_table('products')
```

---

## Timeline: Running `alembic upgrade head`

### Step 1: Alembic Reads Migration Files

```
Alembic scans: alembic/versions/*.py

Found:
├─ 520463b5e478_initial.py
│  ├─ revision: '520463b5e478'
│  ├─ down_revision: None
│  └─ upgrade(): creates products
│
└─ abc123def456_add_description.py (if existed)
   ├─ revision: 'abc123def456'
   ├─ down_revision: '520463b5e478'
   └─ upgrade(): adds description column
```

**What Alembic Learns:**
- Migration 1 has no parent (down_revision=None) → First migration
- Migration 2 points to Migration 1 → Apply in order

---

### Step 2: Connect to Database

```python
# alembic/env.py does this:
database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url)
connection = engine.connect()
```

**Connection established to your database** ✓

---

### Step 3: Check What's Already Applied

```sql
-- Alembic queries the alembic_version table:
SELECT version_num FROM alembic_version;

-- Result (first time):
-- (empty - nothing applied yet)
```

**What Alembic Knows Now:**
- No migrations have been applied yet
- Need to apply: 520463b5e478

---

### Step 4: Load Migration

```python
# Alembic loads the migration file
import alembic.versions.520463b5e478_initial as migration_module

# Gets the upgrade function
upgrade_func = migration_module.upgrade
```

**Loaded:** The upgrade() function from our migration

---

### Step 5: Execute upgrade()

```python
# Alembic calls: upgrade_func()
# This generates SQL:

op.create_table('products',
    sa.Column('id', sa.Integer(), autoincrement=True),
    ...
)

# Which translates to:
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL
);
```

**Generated SQL is executed on database** ✓

---

### Step 6: Record in alembic_version

```sql
-- After migration succeeds, Alembic records it:
INSERT INTO alembic_version (version_num) 
VALUES ('520463b5e478');

-- Check:
SELECT * FROM alembic_version;
-- Result:
-- version_num
-- -----------
-- 520463b5e478
```

**Recorded:** This migration has been applied ✓

---

### Step 7: Repeat for Next Migration (if any)

```python
# Alembic checks: do we have migration abc123def456?
if migration abc123def456 exists:
    # Is it in alembic_version?
    if '520463b5e478' in alembic_version:
        # Prerequisites met! Apply abc123def456
        execute_migration(abc123def456)
        insert into alembic_version (abc123def456)
```

---

## Complete Timeline Visualization

```
DATABASE START STATE:
├─ products table: ✗ doesn't exist
├─ reviews table: ✗ doesn't exist
└─ alembic_version table: ✗ doesn't exist

STEP 1: Alembic connects
├─ Read env.py
├─ Load DATABASE_URL
└─ Connect to database

STEP 2: Check migration status
├─ Query alembic_version
├─ Result: (empty - nothing applied)
└─ Migrations to apply: 520463b5e478

STEP 3: Load migration 520463b5e478
├─ Read alembic/versions/520463b5e478_initial.py
└─ Extract upgrade() function

STEP 4: Execute upgrade()
├─ Run: CREATE TABLE products (...)
├─ Run: CREATE TABLE reviews (...)
└─ Both tables now exist ✓

STEP 5: Record in alembic_version
├─ Run: INSERT INTO alembic_version ('520463b5e478')
└─ Now database knows this migration was applied

DATABASE END STATE:
├─ products table: ✓ exists with correct schema
├─ reviews table: ✓ exists with correct schema
└─ alembic_version table: ✓ contains '520463b5e478'
```

---

## Concrete Example: Two Migrations

### Migration 1: Create Tables

**File:** `alembic/versions/520463b5e478_initial.py`

```python
revision = '520463b5e478'
down_revision = None

def upgrade():
    op.create_table('products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
    )

def downgrade():
    op.drop_table('products')
```

### Migration 2: Add Column

**File:** `alembic/versions/abc123_add_price.py`

```python
revision = 'abc123def456'
down_revision = '520463b5e478'  # ← Points to migration 1!

def upgrade():
    op.add_column('products', 
        sa.Column('price', sa.Numeric(10, 2))
    )

def downgrade():
    op.drop_column('products', 'price')
```

---

## Running `alembic upgrade head`: Step by Step

### BEFORE
```
Database:
├─ products: ✗ 
├─ alembic_version: ✗ (empty)

alembic_version table contents:
(empty - nothing applied)
```

### Run Command
```bash
$ alembic upgrade head
```

### Step-by-step Execution

```
1. Alembic checks alembic_version table
   ├─ Query: SELECT * FROM alembic_version
   └─ Result: (empty)

2. Alembic finds all migrations
   ├─ 520463b5e478 (down_revision=None)
   └─ abc123def456 (down_revision=520463b5e478)

3. Build dependency chain
   ├─ 520463b5e478 has no dependencies → can apply
   └─ abc123def456 depends on 520463b5e478 → apply after

4. Apply migration 520463b5e478
   ├─ Check: Is 520463b5e478 in alembic_version? NO
   ├─ Execute upgrade() function:
   │  └─ CREATE TABLE products (id, name)
   ├─ Record: INSERT INTO alembic_version ('520463b5e478')
   └─ Status: ✓ Applied

5. Apply migration abc123def456
   ├─ Check: Is abc123def456 in alembic_version? NO
   ├─ Check: Is down_revision (520463b5e478) applied? YES
   ├─ Execute upgrade() function:
   │  └─ ALTER TABLE products ADD COLUMN price
   ├─ Record: INSERT INTO alembic_version ('abc123def456')
   └─ Status: ✓ Applied

Done! All migrations applied.
```

### AFTER
```
Database:
├─ products table: ✓ has id, name, price
├─ alembic_version table: ✓ exists

alembic_version table contents:
version_num
-----------
520463b5e478
abc123def456
```

---

## The Magic: How Alembic Knows What to Do

### Scenario 1: First Run (Empty Database)

```python
# In alembic/env.py:

migrations_in_files = [
    '520463b5e478',
    'abc123def456'
]

applied_migrations = query("SELECT * FROM alembic_version")
# Result: []

to_apply = set(migrations_in_files) - set(applied_migrations)
# Result: {'520463b5e478', 'abc123def456'}

# Execute in order (respecting down_revision)
for migration in to_apply:
    execute_upgrade(migration)
    record_in_alembic_version(migration)
```

### Scenario 2: Second Run (Some Already Applied)

```python
migrations_in_files = [
    '520463b5e478',
    'abc123def456'
]

applied_migrations = query("SELECT * FROM alembic_version")
# Result: ['520463b5e478']

to_apply = set(migrations_in_files) - set(applied_migrations)
# Result: {'abc123def456'}  ← Only new ones!

# Execute only the new one
for migration in to_apply:
    execute_upgrade(migration)
    record_in_alembic_version(migration)
```

---

## Downgrade: The Reverse

### Running `alembic downgrade -1`

```
BEFORE:
alembic_version:
├─ 520463b5e478
└─ abc123def456

STEP 1: Query alembic_version
├─ Current revisions: [520463b5e478, abc123def456]
└─ Latest: abc123def456

STEP 2: Load migration abc123def456
├─ Find downgrade() function
└─ It does: op.drop_column('products', 'price')

STEP 3: Execute downgrade()
├─ ALTER TABLE products DROP COLUMN price
└─ Column removed ✓

STEP 4: Remove from alembic_version
├─ DELETE FROM alembic_version 
│  WHERE version_num = 'abc123def456'
└─ Recorded as undone ✓

AFTER:
alembic_version:
└─ 520463b5e478

Database:
└─ products table: only has id, name (price removed)
```

---

## The SQL Alembic Actually Runs

### What We Write (Migration File)
```python
def upgrade():
    op.create_table('products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('price', sa.Numeric(10, 2))
    )
```

### What Alembic Generates (SQL)
```sql
-- For SQLite:
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(10, 2)
);

-- For PostgreSQL:
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(10, 2)
);

-- For MySQL:
CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(10, 2)
);
```

**Same Python code, different SQL per database!** That's why Alembic is so powerful.

---

## The Key Insight: The Dependency Chain

### How Alembic Knows the Order

```
Your migrations:
├─ 520463b5e478_initial.py
│  └─ down_revision = None  ← First!
│
├─ abc123_add_price.py
│  └─ down_revision = '520463b5e478'  ← After first
│
└─ def789_add_rating.py
   └─ down_revision = 'abc123def456'  ← After second

Graph:
None → 520463b5e478 → abc123def456 → def789def789
       ↓               ↓               ↓
       Create          Add price       Add rating
       tables          column          column
```

**Alembic walks this graph** to figure out:
1. What order to apply migrations
2. What order to rollback
3. Which migrations can't be applied yet

---

## Real Execution Log

When you run `alembic upgrade head`, Alembic prints:

```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.autogenerate.compare.tables] Detected added table 'products'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'reviews'
Generating D:\...\alembic\versions\520463b5e478_initial.py ...  done
```

**What's happening:**
1. "Context impl SQLiteImpl" → Using SQLite dialect
2. "Detected added table" → Comparing ORM to database
3. "Generating migration" → Creating the migration file

---

## Summary: Alembic Internals

### The Three Key Files

1. **Migration files** (alembic/versions/*.py)
   - Contains upgrade() and downgrade()
   - Tracks revision and down_revision

2. **alembic_version table** (in your database)
   - Stores which migrations have been applied
   - Acts as the "truth" for what's installed

3. **env.py** (alembic/env.py)
   - Reads migrations from files
   - Compares with alembic_version table
   - Executes upgrades/downgrades

### How They Work Together

```
env.py reads files → Migration files
                    ↓
                Gets upgrade() & downgrade()
                    ↓
                Queries alembic_version table
                    ↓
                Figures out which to apply
                    ↓
                Executes SQL
                    ↓
                Updates alembic_version table
```

### The Loop

```
User runs:           alembic upgrade head
                     ↓
Alembic loads:       All .py files from versions/
                     ↓
Alembic checks:      What's in alembic_version?
                     ↓
Alembic calculates:  What's missing?
                     ↓
Alembic executes:    upgrade() functions in order
                     ↓
Alembic records:     INSERT into alembic_version
                     ↓
Result:              Database updated, version tracked
```

---

## Why This Design Is Brilliant

### Problem It Solves

```
❌ Without alembic_version table:
├─ How do we know what's been applied?
├─ Did we run migration 1? 2? Both?
└─ No record → No safety

✅ With alembic_version table:
├─ One source of truth
├─ Easy to query: SELECT * FROM alembic_version
└─ Alembic knows exactly what's installed
```

### Why Dependency Chain Matters

```
❌ Without down_revision:
├─ Apply migrations randomly
├─ Migration 2 before 1?
└─ Crash! Dependencies not met

✅ With down_revision:
├─ Can build dependency graph
├─ Apply in correct order
└─ Respects dependencies
```

### Why Files in alembic/versions/ Matter

```
❌ Without migration files:
├─ How do we undo?
├─ No downgrade() function
└─ No way to rollback safely

✅ With migration files:
├─ Each file has upgrade() AND downgrade()
├─ Can apply or revert
└─ Fully reversible
```

---

## Putting It All Together

When you run `alembic upgrade head` on your project:

```
1. Alembic connects to SQLite database
   ├─ DATABASE_URL = sqlite:///./review_db.sqlite
   └─ Connection successful ✓

2. Alembic loads all migration files
   ├─ 520463b5e478_initial.py
   └─ (Plus any others if they existed)

3. Alembic checks alembic_version table
   ├─ First run: table doesn't exist
   └─ Alembic creates it

4. Alembic compares files vs table
   ├─ Files: 520463b5e478
   ├─ Table: (empty)
   └─ To apply: 520463b5e478

5. Alembic executes migration 520463b5e478
   ├─ Runs upgrade() function
   ├─ Creates products table ✓
   ├─ Creates reviews table ✓
   └─ Both tables ready to use

6. Alembic records in alembic_version
   ├─ INSERT INTO alembic_version ('520463b5e478')
   └─ Marked as applied ✓

RESULT: Database is set up, ready to use! 🎉
```

That's how Alembic works internally!
