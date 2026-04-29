# Schema Documentation - Deployment & Usage Guide

**Target:** DBAs, System Administrators, Developers  
**Purpose:** Organization, navigation, and deployment procedures for the Exception Management System schema

---

## 📁 Folder Structure

```
backend/
├── SCHEMA_DOCUMENTATION/                    ← You are here
│   ├── README.md                            ← Navigation & quick facts
│   ├── DBMS_SCHEMA_REFERENCE.md             ← Complete DBMS reference
│   ├── ER_DIAGRAM_VISUAL.md                 ← ER diagram & data flow
│   ├── SQL_QUERIES_REFERENCE.md             ← Operational SQL patterns
│   └── DEPLOYMENT_GUIDE.md                  ← This file
│
├── SCHEMA_FINAL_TECHNICAL_v1.md             ← Design & architecture
├── SCHEMA_AUDIT_v1.md                       ← Audit trail & compliance
├── SCHEMA_FREEZE_CHECKLIST.md               ← Certification & readiness
├── DB_README.md                             ← Database setup & migration
│
├── requirements.txt
├── manage.py
├── db.sqlite3                               ← Dev SQLite (Django)
├── schema_validation.py                     ← Validation checker
├── test_checkpoint_workflow.py               ← Workflow test suite
│
└── exceptions/
    ├── models.py
    ├── serializers.py
    ├── migrations/
    │   ├── 0001_initial.py
    │   ├── ...
    │   ├── 0008_schema_freeze_validations.py
    │   ├── 0009_remove_assigned_risk_owner.py
    │   └── 0010_normalize_index_names.py
    └── ...
```

---

## 🚀 Quick Start for Mentors

### 1. **First Time? Start Here:**

Read in this order (20 minutes):

1. [README.md](README.md) — Navigation guide + key facts (2 min)
2. [../SCHEMA_FREEZE_CHECKLIST.md](../SCHEMA_FREEZE_CHECKLIST.md) — Status overview (5 min)
3. [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) — Core domain tables section (10 min)
4. [ER_DIAGRAM_VISUAL.md](ER_DIAGRAM_VISUAL.md) — Skim diagrams (3 min)

**Result:** You understand the complete schema, what's implemented, and why.

---

### 2. **For Deployment:**

Follow [../DB_README.md](../DB_README.md):

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Apply migrations
python manage.py migrate

# 3. Load reference data
python manage.py seed_master_data
python manage.py seed_org_data
python manage.py seed_extended_data

# 4. Validate schema
python schema_validation.py

# 5. Run tests
python manage.py test exceptions.tests
python test_checkpoint_workflow.py
```

**Expected result:** All green ✅, no errors

---

### 3. **For Code Review:**

Read [../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md) + [../SCHEMA_AUDIT_v1.md](../SCHEMA_AUDIT_v1.md)

Focus on:
- Status state machine (why transitions are locked)
- Permission model (role-based access via groups)
- Constraint philosophy (PROTECT vs. CASCADE vs. SET_NULL)

---

### 4. **For Database Tuning:**

Read [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → Constraints & Indexes section

Run queries from [SQL_QUERIES_REFERENCE.md](SQL_QUERIES_REFERENCE.md) to verify performance

---

## 📋 Document Index & Purposes

| Document | Format | Audience | Read Time | Key Sections |
|----------|--------|----------|-----------|--------------|
| **README.md** | Markdown | Everyone | 5 min | Navigation, quick facts, file org |
| **DBMS_SCHEMA_REFERENCE.md** | Markdown | DBAs, Architects, Developers | 20 min | Tables, columns, types, constraints, indexes, DDL |
| **ER_DIAGRAM_VISUAL.md** | Markdown + ASCII | Architects, Developers | 10 min | ER diagram, state machine, data flow, relationship matrix |
| **SQL_QUERIES_REFERENCE.md** | SQL + Markdown | DBAs, Support, Developers | 15 min | Operational queries, troubleshooting, performance checks |
| **SCHEMA_FINAL_TECHNICAL_v1.md** (parent) | Markdown | Architects, Developers, Reviewers | 15 min | Design decisions, API contract, validation rules, rationale |
| **SCHEMA_AUDIT_v1.md** (parent) | Markdown | Compliance, Security, Auditors | 10 min | Audit trail, permission model, data retention |
| **SCHEMA_FREEZE_CHECKLIST.md** (parent) | Markdown | Project Managers, Mentors | 5 min | Certification, risk assessment, readiness |
| **DB_README.md** (parent) | Markdown | DBAs, System Admins, Developers | 10 min | Setup, migrations, seeding, testing, backup |

---

## 🔍 How to Use This Documentation

### I want to understand the database structure

**Read:** [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md)

This is the authoritative technical reference with:
- Complete table definitions (columns, types, nullability, defaults)
- All constraints (CHECK, FK, UNIQUE, PRIMARY KEY)
- Index strategy for performance
- Foreign key behaviors (PROTECT vs. CASCADE vs. SET_NULL)
- Validation rules (ORM + DB level)

---

### I need to write an SQL query

**Read:** [SQL_QUERIES_REFERENCE.md](SQL_QUERIES_REFERENCE.md)

Copy-paste patterns for:
- Finding pending approvals
- Querying audit trail
- Dashboard filtering
- Data quality checks
- Troubleshooting

All queries are parameterized and production-ready.

---

### I'm debugging a schema issue

**Start with:** [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → Data Consistency Notes

Then use queries from [SQL_QUERIES_REFERENCE.md](SQL_QUERIES_REFERENCE.md) → Troubleshooting Queries

---

### I need to understand the workflow

**Read:** [ER_DIAGRAM_VISUAL.md](ER_DIAGRAM_VISUAL.md) → Status State Machine + Data Flow Diagram

Also see [../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md) → Status State Machine section

---

### I'm integrating with the API

**Read:** [../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md) → API Contract

Reference [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → API Surface Contract section

---

### I need to verify schema before production

**Follow:** [../SCHEMA_FREEZE_CHECKLIST.md](../SCHEMA_FREEZE_CHECKLIST.md) → Certification Checklist

Run: `python schema_validation.py` (should show "SCHEMA FREEZE READY")

---

### Setup is failing / migrations not applying

**Read:** [../DB_README.md](../DB_README.md) → Troubleshooting section

Run: `python schema_validation.py --verbose` for diagnostic output

---

## 🔐 Data Integrity & Constraints

### Key Validations (Applied at Multiple Layers)

| Validation | Level | Error Type |
|-----------|-------|-----------|
| `number_of_assets >= 1` | DB + ORM | IntegrityError / ValidationError |
| `risk_score >= 0 or NULL` | DB + ORM | IntegrityError / ValidationError |
| `risk_owner.is_active` | Serializer | ValidationError + HTTP 400 |
| `risk_owner in RiskOwner group` | Serializer | ValidationError + HTTP 400 |
| `assigned_approver == bu.cio` | Serializer | ValidationError + HTTP 400 |
| `exception_end_date > now()` | Serializer | ValidationError + HTTP 400 |
| Status transitions valid | ORM Signal | Exception + rollback |

**Philosophy:** Database (PostgreSQL) handles structural integrity; ORM/Serializer handles business logic.

---

## 📊 Performance Indexes

Critical indexes for production:

| Index Name | Columns | Purpose | Query Pattern |
|-----------|---------|---------|--------------|
| `exception_status_deadline_idx` | (status, approval_deadline) | Scheduler: pending approvals | WHERE status='AwaitingRiskOwner' AND deadline < now() |
| `exception_status_enddate_idx` | (status, exception_end_date) | Expiration checks | WHERE status IN (...) AND enddate < now() |
| `exc_reminder_deadln_idx` | (reminder_stage, deadline) | Reminder scheduling | WHERE stage='Stage1' AND deadline < date+5days |
| `exception_bu_status_idx` | (business_unit_id, status) | Dashboard filters | WHERE bu=X AND status=Y |
| `auditlog_exc_ts_idx` | (exception_request_id, timestamp) | Audit trail lookup | WHERE req_id=X ORDER BY ts DESC |

**Action:** Verify these indexes exist in production:

```bash
python manage.py shell
>>> from django.db import connection
>>> cursor = connection.cursor()
>>> cursor.execute("SELECT * FROM pg_indexes WHERE tablename LIKE 'exceptions_%'")
>>> for row in cursor.fetchall(): print(row)
```

---

## 🚚 Deployment Checklist

### Pre-Deployment

- [ ] All migrations applied locally: `python manage.py migrate`
- [ ] Tests passing: `python manage.py test exceptions.tests`
- [ ] Workflow validation: `python test_checkpoint_workflow.py`
- [ ] Schema validated: `python schema_validation.py` → "SCHEMA FREEZE READY"
- [ ] Code review complete: [../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md)
- [ ] No pending migrations: `python manage.py makemigrations --dry-run` → "No changes"

### Deployment Steps

1. **Database backup** (production):
   ```bash
   pg_dump -U postgres my_database > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Apply migrations**:
   ```bash
   python manage.py migrate --noinput
   ```

3. **Verify constraints**:
   ```bash
   python schema_validation.py
   ```

4. **Load reference data** (if empty):
   ```bash
   python manage.py seed_master_data
   ```

5. **Smoke test**:
   ```python
   from exceptions.models import ExceptionRequest, BusinessUnit
   assert BusinessUnit.objects.count() > 0
   assert ExceptionRequest.objects.count() >= 0
   ```

### Post-Deployment

- [ ] Verify all tables exist
- [ ] Verify constraints active
- [ ] Verify indexes created
- [ ] Monitor error logs (first 24h)
- [ ] Verify scheduler is running

---

## 🔧 Maintenance Tasks

### Weekly

- [ ] Check failed reminders: 
  ```sql
  SELECT COUNT(*) FROM exceptions_reminderlog WHERE delivery_status='failed' AND sent_at > NOW() - INTERVAL '7 days';
  ```
- [ ] Verify no stuck approvals:
  ```sql
  SELECT COUNT(*) FROM exceptions_exceptionrequest WHERE status='AwaitingRiskOwner' AND approval_deadline < NOW();
  ```

### Monthly

- [ ] Review index usage statistics
- [ ] Check table bloat (run VACUUM ANALYZE)
- [ ] Archive old audit logs (if retention policy applies)
- [ ] Review orphaned audit logs (should be 0 in production)

### Quarterly

- [ ] Full schema backup
- [ ] Test disaster recovery plan
- [ ] Review slow query logs

---

## 🆘 Troubleshooting

### Problem: Migrations failing

**Check:**
1. Database connectivity: `python manage.py dbshell`
2. Migration status: `python manage.py showmigrations`
3. Schema validation: `python schema_validation.py`

**See:** [../DB_README.md](../DB_README.md) → Troubleshooting

---

### Problem: Scheduler not running / reminders not sent

**Check:**
1. Scheduler process alive: `ps aux | grep celery` or `ps aux | grep APScheduler`
2. Recent reminder logs: `SELECT * FROM exceptions_reminderlog ORDER BY sent_at DESC LIMIT 5;`
3. Pending approvals: `SELECT COUNT(*) FROM exceptions_exceptionrequest WHERE status='AwaitingRiskOwner' AND approval_deadline < NOW();`

**See:** [SQL_QUERIES_REFERENCE.md](SQL_QUERIES_REFERENCE.md) → Reminder Delivery Status

---

### Problem: API returning unexpected validation error

**Check:**
1. Serializer validation rules: [../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md) → Validation Rules
2. ORM constraints: [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → Validation Rules (ORM + Serializer)
3. Database constraints: Run `python schema_validation.py --verbose`

---

### Problem: Slow queries

**Check:**
1. Index usage: [SQL_QUERIES_REFERENCE.md](SQL_QUERIES_REFERENCE.md) → Performance & Index Verification
2. Table bloat: Run VACUUM ANALYZE
3. Query plan: Prefix query with EXPLAIN ANALYZE

---

## 📞 Support & Questions

### Document Questions

| Question | Answer Location |
|----------|-----------------|
| What tables exist? | [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → Core Domain Tables |
| What's the ER diagram? | [ER_DIAGRAM_VISUAL.md](ER_DIAGRAM_VISUAL.md) → ER Diagram |
| How does workflow work? | [ER_DIAGRAM_VISUAL.md](ER_DIAGRAM_VISUAL.md) → Status State Machine + Data Flow |
| What are the constraints? | [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → Constraints & Data Integrity |
| Which indexes are critical? | [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md) → Indexes for Performance |
| How do I query X? | [SQL_QUERIES_REFERENCE.md](SQL_QUERIES_REFERENCE.md) → Find relevant section |
| Is schema production-ready? | [../SCHEMA_FREEZE_CHECKLIST.md](../SCHEMA_FREEZE_CHECKLIST.md) → ✅ Yes |
| What was the design rationale? | [../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md) → Design & Constraints Sections |
| How do I deploy? | [../DB_README.md](../DB_README.md) → Deployment Instructions |

---

## ✅ Verification Checklist

Run these to verify schema is properly deployed:

```bash
# 1. Django check (no errors)
python manage.py check
# Expected: System check identified no issues (0 silenced).

# 2. Migrations status (all applied)
python manage.py showmigrations exceptions
# Expected: All migrations marked [X]

# 3. No pending migrations
python manage.py makemigrations --dry-run
# Expected: No changes detected

# 4. Schema validation (comprehensive)
python schema_validation.py
# Expected: SCHEMA FREEZE READY (14 checks passed, 0 errors, 1 non-blocking warning)

# 5. Tables exist
python manage.py dbshell
>>> SELECT COUNT(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'exceptions_%';
# Expected: 15+ rows

# 6. Constraints exist
python manage.py dbshell
>>> SELECT COUNT(*) FROM pg_constraint WHERE conname LIKE 'exception_%';
# Expected: 25+ rows

# 7. Indexes exist
python manage.py dbshell
>>> SELECT COUNT(*) FROM pg_indexes WHERE tablename LIKE 'exceptions_%';
# Expected: 12+ indexes

# 8. Tests passing
python manage.py test exceptions.tests
# Expected: 6 OK

# 9. Workflow validation
python test_checkpoint_workflow.py
# Expected: All assertions pass
```

---

## 📝 Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| v0010 | 2026-03-27 | ✅ FINAL | Index name normalization, schema freeze complete |
| v0009 | 2026-03-15 | Applied | Removed assigned_risk_owner field (redundant) |
| v0008 | 2026-03-01 | Applied | Added CHECK constraints & scheduler indexes |
| v0001–v0007 | 2026-01-15 to 2026-02-25 | Applied | Core schema + feature development |

**Current Status:** Production Ready (v1)  
**No Pending Migrations:** YES ✅  
**Schema Locked:** YES ✅  

---

## 🎯 Key Takeaways

1. **Schema is frozen** — v0010 applied, no pending changes
2. **Fully validated** — 14 checks pass, 1 non-blocking warning
3. **Production-ready** — All tests green, constraints active
4. **Well-documented** — Complete reference in this folder
5. **Organized** — Quick reference for common tasks (README.md, SQL_QUERIES_REFERENCE.md)

**Next Step:** Deploy to production following [../DB_README.md](../DB_README.md)

---

**Generated:** 2026-03-27  
**Status:** ✅ Production Ready  
**Mentor Review:** Complete
