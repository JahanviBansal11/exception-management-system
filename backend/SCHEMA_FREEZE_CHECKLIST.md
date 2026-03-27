# Schema Freeze Execution Checklist v1.0

**Timeline:** 2–3 hours  
**Date:** Complete before end of Week 1 (by April 2)  
**Owner:** You  
**Validator:** Run `schema_validation.py` at each step

---

## Pre-Execution Checklist

- [ ] **Backup current database**
  ```bash
  # Docker backup
  docker exec exception-postgres pg_dump -U postgres grc_exceptions > backup_pre_freeze_$(date +%Y%m%d).sql
  
  # Or local SQLite
  cp db.sqlite3 db.sqlite3.backup
  ```

- [ ] **Confirm all tests pass**
  ```bash
  python manage.py test exceptions.tests
  python test_checkpoint_workflow.py
  ```

- [ ] **Review SCHEMA_AUDIT_v1.md** for context on the 5 critical fixes

---

## Execution Steps

### Step 1: Run Pre-Migration Validation (10 min)
```bash
cd backend
python schema_validation.py
```

**Expected output:**
```
✓ All exceptions have number_of_assets >= 1
✓ All risk_scores are NULL or >= 0
✓ All risk_ratings are valid
⚠ Constraint [constraint_name] NOT YET created (will be in migration)
✓ Status transition matrix is correct
```

**If errors:** Fix data before proceeding (see Data Remediation section below)

---

### Step 2: Inspect Migration (5 min)
```bash
cd backend
python manage.py showmigrations exceptions | grep 0008
```

**Should show:**
```
 [ ] 0008_schema_freeze_validations
```

**Review migration file:**
```bash
cat exceptions/migrations/0008_schema_freeze_validations.py
```

Verify it includes:
- ✓ risk_rating with choices
- ✓ number_of_assets constraint
- ✓ risk_score constraint
- ✓ Scheduler indexes (status, approval_deadline), etc.

---

### Step 3: Run Migration Dry-Run (10 min)
```bash
python manage.py migrate --plan exceptions 0008_schema_freeze_validations
```

**Expected:** Lists all SQL operations to be executed.

```bash
# If using PostgreSQL, test syntax
python manage.py sqlmigrate exceptions 0008_schema_freeze_validations
```

---

### Step 4: Apply Migration (15 min)
```bash
python manage.py migrate exceptions 0008_schema_freeze_validations
```

**Expected output:**
```
Running migrations:
  Applying exceptions.0008_schema_freeze_validations... OK
```

**If errors:** Consult the Rollback section

---

### Step 5: Post-Migration Validation (10 min)
```bash
python schema_validation.py
```

**Expected output:**
```
✓ All indexes created
✓ All constraints enforced
✓ Status transition matrix correct
✓ All referential integrity checks pass

✅ SCHEMA FREEZE READY
```

**If warnings:** Document and proceed if data quality is acceptable

---

### Step 6: Re-Run Test Suite (15 min)
```bash
# Unit tests
python manage.py test exceptions.tests

# Workflow tests
python test_checkpoint_workflow.py
```

**Expected:** All tests pass

---

### Step 7: Document & Lock Schema
1. Create `SCHEMA_v1_FROZEN.md`:
   ```markdown
   # Schema v1.0 Frozen
   **Date:** [Today]
   **Locked By:** [Your name]
   **Migration:** 0008_schema_freeze_validations
   
   ## Allowed Changes:
   - Additive migrations only (new fields, new tables)
   - No structural changes to existing tables
   - No constraint modifications
   
   ## Forbidden Changes:
   - Removing fields
   - Removing constraints
   - Widening data types
   - Renaming columns
   ```

2. Create `migrations/migration_policy.md`:
   ```markdown
   # Migration Policy (Effective after Schema v1.0 Freeze)
   
   ## Release Process
   1. Write migration
   2. Run `python manage.py makemigrations`
   3. Run `schema_validation.py`
   4. All tests must pass
   5. All migrations must be reversible via `python manage.py migrate <prev>`
   
   ## Naming Convention
   - Additive: `NNNN_add_[description].py`
   - Bug fix: `NNNN_fix_[description].py`
   - Data: `NNNN_populate_[description].py`
   ```

---

## Data Remediation (if needed)

### Check for Invalid Data

```bash
python manage.py shell
```

```python
from exceptions.models import ExceptionRequest

# Find exceptions with invalid number_of_assets
invalid = ExceptionRequest.objects.filter(number_of_assets__lt=1)
print(f"Found {invalid.count()} exceptions with number_of_assets < 1")

for exc in invalid:
    print(f"  ID {exc.id}: number_of_assets = {exc.number_of_assets}")

# Find exceptions with negative risk_score
invalid_score = ExceptionRequest.objects.filter(risk_score__isnull=False, risk_score__lt=0)
print(f"Found {invalid_score.count()} with negative risk_score")

# Find invalid risk_rating
valid_ratings = ['Low', 'Medium', 'High', 'Critical', '']
invalid_rating = ExceptionRequest.objects.exclude(risk_rating__in=valid_ratings)
print(f"Found {invalid_rating.count()} with invalid risk_rating")
```

### Fix Data (if found)

```python
# Fix number_of_assets
for exc in ExceptionRequest.objects.filter(number_of_assets__lt=1):
    exc.number_of_assets = 1
    exc.save()

# Fix risk_rating
for exc in ExceptionRequest.objects.filter(risk_score__isnull=False, risk_score__in=[]):
    # Recalculate
    score = exc.calculate_risk_score()
    rating = exc.determine_risk_rating(score)
    exc.risk_score = score
    exc.risk_rating = rating
    exc.save()
```

---

## Rollback (if migration fails)

```bash
# Reverse migration
python manage.py migrate exceptions 0007_rename_riskissue_table_and_constraints

# Restore backup
docker exec exception-postgres psql -U postgres -d grc_exceptions < backup_pre_freeze_*.sql
# OR
cp db.sqlite3.backup db.sqlite3
```

---

## Post-Freeze Actions

1. **Mark schema as frozen** in code comments
2. **Update README.md** with migration policy
3. **Notify team:** Schema is now locked; all changes require review
4. **Schedule week 2:** Begin data seeding strategy

---

## Timeline Summary

| Step | Time | Status |
|------|------|--------|
| 1. Backup + validate | 10 min | ⬜ |
| 2. Inspect migration | 5 min | ⬜ |
| 3. Dry-run | 10 min | ⬜ |
| 4. Apply | 15 min | ⬜ |
| 5. Post-validation | 10 min | ⬜ |
| 6. Test suite | 15 min | ⬜ |
| 7. Documentation | 10 min | ⬜ |
| **TOTAL** | **~2 hrs** | ⬜ |

---

## Success Criteria

After completion:
- ✅ All migrations applied successfully
- ✅ All tests pass (unit + workflow)
- ✅ `schema_validation.py` shows "SCHEMA FREEZE READY"
- ✅ No data integrity errors
- ✅ All indexes exist in database
- ✅ All constraints enforced
- ✅ Documentation updated

If all ✅, proceed to **Week 2: Data Seeding** phase.

