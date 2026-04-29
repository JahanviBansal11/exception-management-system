# Schema Documentation Index

**Last Updated:** 2026-03-27  
**Status:** ✅ Production-Ready (v1)  
**Target Audience:** Mentors, DBAs, Architects, Developers

---

## Quick Navigation

### For Database Administrators & Architects

Start with **[DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md)**
- Complete table-by-table reference with all columns, types, constraints, indexes
- Operational query patterns used by scheduler, dashboard, audit functions
- Migration timeline & schema freeze certification

### For Developers & API Consumers

Start with **[../SCHEMA_FINAL_TECHNICAL_v1.md](../SCHEMA_FINAL_TECHNICAL_v1.md)**
- Entity relationships & design decisions
- Status state machine & workflow rules
- API field mappings (serializer contract)
- Validation rules for each entity

### For Auditors & Compliance Teams

Start with **[../SCHEMA_AUDIT_v1.md](../SCHEMA_AUDIT_v1.md)**
- Audit log design & immutability guarantees
- Permission model (role-based access via groups)
- Data retention policies
- Validation evidence & test results

### For Project Managers & Handoff

Read: **[../SCHEMA_FREEZE_CHECKLIST.md](../SCHEMA_FREEZE_CHECKLIST.md)**
- Certification checklist (v0010 = all items ✓)
- Risk assessment (what was removed, why it's safe)
- Deployment readiness assessment
- Known non-blocking issues

### For Operational Deployment

See: **[../DB_README.md](../DB_README.md)**
- Database initialization instructions
- Migration execution steps
- Seed data loading (reference tables)
- Testing & validation
- Backup & recovery procedures

---

## Document Overview

### 1. DBMS_SCHEMA_REFERENCE.md (THIS FOLDER)

**Technical DBMS-style reference** of the complete database schema.

**Sections:**
- Entity overview (table summary)
- Core domain tables (ExceptionRequest, AuditLog, ExceptionCheckpoint, ReminderLog) — detailed column definitions, constraints, indexes
- Reference/lookup tables (ExceptionType, BusinessUnit, RiskIssue, dimensional tables)
- Django authentication integration (User, Group role definitions)
- Constraints & data integrity (CHECK, FK behaviors, PROTECT vs. SET_NULL)
- Indexes for performance (scheduler-critical, dashboard, standard FK)
- Migration timeline (0001–0010 changes & status)
- API surface contract (serializer explicit fields)
- Validation rules (ORM + serializer checks)
- Operational queries (SQL patterns for common tasks)
- Data consistency notes (orphaned logs explanation)
- Schema freeze certification (✅ production-ready v1)

**Best For:** Understanding actual database structure, performance tuning, writing reports/queries

---

### 2. ../SCHEMA_FINAL_TECHNICAL_v1.md (BACKEND ROOT)

**Narrative technical document** focused on design & architecture.

**Sections:**
- Executive summary (problem statement, solution overview)
- Data model (entity descriptions, attributes, relationships)
- Constraint philosophy (why PROTECT vs. CASCADE, why SET_NULL for audit)
- Field design notes (e.g., why `approval_deadline` is nullable)
- Status state machine (allowed transitions, scheduler enforcement)
- Permission model (role-based access, group assignments)
- API contract (serializer fields, validation logic)
- Migration strategy (batching, safety rationale)
- Validation evidence (test results, schema checks)
- Known issues & non-blocking warnings

**Best For:** Understanding *why* decisions were made, design rationale, code review

---

### 3. ../SCHEMA_AUDIT_v1.md (BACKEND ROOT)

**Audit trail & compliance documentation.**

**Sections:**
- AuditLog design (immutability, SET_NULL rationale, JSON payload structure)
- Permission model (canonical vs. legacy group names, role enforcement)
- Data retention policies
- Orphaned record explanation (test cleanup, expected in dev only)
- Validation evidence (14 checks passed, 1 non-blocking warning)
- Compliance references

**Best For:** Demonstrating audit capabilities, compliance requirements, security review

---

### 4. ../SCHEMA_FREEZE_CHECKLIST.md (BACKEND ROOT)

**Certification & readiness assessment.**

**Sections:**
- ✓ Schema freeze checklist (migrations finalized, no pending changes)
- ✓ Risk assessment (what was removed—assigned_risk_owner, why it's safe)
- ✓ Deployment readiness (all tests passing, no migration issues)
- ⚠️ Known issues (152 orphaned logs from test cleanup, non-blocking)

**Best For:** Handoff sign-off, mentor review, deployment approval

---

### 5. ../DB_README.md (BACKEND ROOT)

**Operational procedures & deployment guide.**

**Sections:**
- Database setup (PostgreSQL 13+)
- Migration execution (`manage.py migrate`)
- Seed data loading (reference tables via management commands)
- Testing procedures (unit tests, workflow validation)
- Schema validation script (`python schema_validation.py`)
- Backup & recovery
- Troubleshooting

**Best For:** Getting system running, executing migrations, running tests

---

## Key Takeaways for Mentors

### ✅ What's Complete

1. **Schema finalized** — 10 migrations applied, no pending changes
2. **Data integrity** — Check constraints (assets ≥ 1, risk_score ≥ 0) enforced at DB & ORM level
3. **Audit trail** — Immutable AuditLog with timezone-aware timestamps
4. **Workflow enforcement** — Status state machine + checkpoint tracking
5. **Permission model** — Role-based access via Django groups (RiskOwner, Approver, Requestor, Security)
6. **Performance** — 12+ indexes optimized for scheduler queries, dashboard filtering
7. **API contract** — Explicit serializer fields (no `__all__`), stable API surface
8. **Testing** — 6/6 unit tests passing, full workflow validation green

### ⚠️ Non-Blocking Issues

- **152 orphaned audit logs** from test cleanup (design is correct; SET_NULL allows logs to survive user deletion)
- No functional impact on production data
- Expected in development; live system will not have orphaned logs

### 🚀 Ready For

- Production deployment to PostgreSQL
- Mentor code review
- User acceptance testing (UAT)
- Live exception management operations

---

## How to Read This Documentation

**Option 1: Comprehensive Review (30 min)**
1. Skim this index (2 min)
2. Read SCHEMA_FREEZE_CHECKLIST.md (5 min) — status overview
3. Read DBMS_SCHEMA_REFERENCE.md (Overview + key tables) (15 min) — actual schema
4. Skim SCHEMA_FINAL_TECHNICAL_v1.md (8 min) — design rationale

**Option 2: DBA Focus (20 min)**
1. Read DBMS_SCHEMA_REFERENCE.md (tables, constraints, indexes, queries) (15 min)
2. Read DB_README.md (deployment & procedures) (5 min)

**Option 3: Architect Focus (25 min)**
1. Read SCHEMA_FINAL_TECHNICAL_v1.md (design, state machine, permission model) (15 min)
2. Read DBMS_SCHEMA_REFERENCE.md (validation rules, operational queries) (10 min)

**Option 4: Compliance/Audit Focus (20 min)**
1. Read SCHEMA_AUDIT_v1.md (audit trail, permission model, validation) (15 min)
2. Read DBMS_SCHEMA_REFERENCE.md (constraints, FK behaviors) (5 min)

---

## File Organization

```
backend/
├── SCHEMA_DOCUMENTATION/
│   ├── README.md (this file)
│   ├── DBMS_SCHEMA_REFERENCE.md              ← START HERE for tables/columns/indexes
│   └── (companion docs reference parent files)
├── SCHEMA_FINAL_TECHNICAL_v1.md              ← Design rationale & API contract
├── SCHEMA_AUDIT_v1.md                        ← Audit trail & compliance
├── SCHEMA_FREEZE_CHECKLIST.md                ← Certification & readiness
├── DB_README.md                              ← Deployment & operations
├── schema_validation.py                      ← Validation checks runner
├── requirements.txt                          ← Dependencies
├── db.sqlite3                                ← SQLite for dev/test
├── generate_schema_dbms_doc.py               ← Tool used to generate this doc
└── exceptions/
    └── models.py, serializers.py, etc.
```

---

## Quick Facts

| Aspect | Detail |
|--------|--------|
| **Database** | PostgreSQL 13+ |
| **Framework** | Django 4.2 LTS |
| **Migrations** | 10 total (0001–0010), all applied |
| **Core Tables** | 4 (ExceptionRequest, AuditLog, ExceptionCheckpoint, ReminderLog) |
| **Reference Tables** | 9 (ExceptionType, BusinessUnit, RiskIssue, dimensions) |
| **Total Tables** | 25+ (including Django auth/admin tables) |
| **Check Constraints** | 2 (number_of_assets ≥ 1, risk_score ≥ 0 or NULL) |
| **Indexes** | 12+ optimized for scheduler, dashboard, FK lookups |
| **API Fields** | 40+ (explicit serializer list, no `__all__`) |
| **Status Values** | 7 enum choices (Draft, Submitted, AwaitingRiskOwner, Approved, Rejected, Expired, Closed) |
| **Roles** | 4 (RiskOwner, Approver, Requestor, Security) |
| **Test Coverage** | 6/6 unit tests passing, workflow E2E validated |
| **Schema Validation** | 14/15 checks green, 1 non-blocking warning |

---

## Contact & Support

For questions on this documentation:

- **Schema/Database Questions** → See DBMS_SCHEMA_REFERENCE.md + DB_README.md
- **Design Decisions** → See SCHEMA_FINAL_TECHNICAL_v1.md
- **Audit/Compliance** → See SCHEMA_AUDIT_v1.md
- **Deployment Readiness** → See SCHEMA_FREEZE_CHECKLIST.md
- **Getting Started** → See DB_README.md

---

**Status:** ✅ Production Ready (v1)  
**Generated:** 2026-03-27  
**Schema Freeze:** Final (no pending migrations)
