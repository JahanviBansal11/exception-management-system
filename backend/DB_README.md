# Database Schema Documentation

**Last Updated:** March 27, 2026  
**Version:** 1.0 (Frozen)  
**Environment:** PostgreSQL 15+  
**Canonical Source:** Django ORM models (`backend/exceptions/models.py`)  

---

## Quick Start

### Fresh Environment Setup
```bash
# 1. Apply all migrations
python manage.py migrate

# 2. Seed master data (risk weights, asset types, classifications)
python manage.py seed_master_data

# 3. Seed org roles and demo users
python manage.py seed_org_data

# 4. Seed business units, exception types, risk issues
python manage.py seed_extended_data

# 5. Validate schema
python manage.py validate_db_schema
```

### Connection String
```
postgresql://postgres:password@localhost:5432/grc_exceptions
```

### Async Notifications / Scheduler Notes

The project supports two execution modes for emails and reminders:

- **Industry mode:** Redis + Celery worker + Celery beat
    - Set `CELERY_TASK_ALWAYS_EAGER=False`
    - Keep `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` pointed at Redis
    - Run the worker and beat processes continuously

- **Local mode:** no Redis required
    - Set `CELERY_TASK_ALWAYS_EAGER=True`
    - Action-triggered emails run inline
    - Reminder schedules will not execute automatically unless a scheduler/job runner calls the task entrypoints

Recommended production pattern: use Redis for broker/result backend, SMTP for email transport, and keep SendGrid optional rather than mandatory.

---

## Entity Relationship Diagram (ERD)

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXCEPTION WORKFLOW                            │
│                                                                   │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │  auth_user       │         │  auth_group      │              │
│  ├──────────────────┤         ├──────────────────┤              │
│  │ id (PK)          │         │ id (PK)          │              │
│  │ username (UQ)    │         │ name (UQ)        │              │
│  │ email            │────┐    │                  │              │
│  │ first_name       │    │    │ Groups:          │              │
│  │ last_name        │    │    │  - Requestor     │              │
│  │ is_active        │    │    │  - Approver      │              │
│  └──────────────────┘    │    │  - RiskOwner     │              │
│         ▲                │    │  - Security      │              │
│         │ (M2M)          │    └──────────────────┘              │
│         │                │                                       │
│  ┌──────────────────┐    │                                       │
│  │ auth_user_groups │    │                                       │
│  └──────────────────┘    │                                       │
│                          │                                       │
│         ┌────────────────┴──────────────────┐                   │
│         │                                   │                   │
│  ┌─────▼────────────────┐  ┌──────────────▼─────┐              │
│  │ ExceptionRequest     │  │  BusinessUnit      │              │
│  ├──────────────────────┤  ├────────────────────┤              │
│  │ id (PK)              │  │ id (PK)            │              │
│  │ status (FK enum)     │  │ bu_code (UQ)       │              │
│  │ business_unit_id (FK)├─→│ name (UQ)          │              │
│  │ exception_type_id(FK)│  │ cio_id (FK→User)   │              │
│  │ risk_issue_id (FK)   │  └────────────────────┘              │
│  │ requested_by_id (FK) │                                       │
│  │ assigned_approver_id │  ┌────────────────────┐              │
│  │ risk_owner_id (FK)   │  │ ExceptionType      │              │
│  │ approval_deadline    │  ├────────────────────┤              │
│  │ approved_at          │  │ id (PK)            │              │
│  │ exception_end_date   │  │ name (UQ)          │              │
│  │ risk_score           │  │ approval_sla_days  │              │
│  │ risk_rating          │  └────────────────────┘              │
│  │ reminder_stage       │                                       │
│  │ created_at (indexed) │  ┌────────────────────┐              │
│  │ updated_at           │  │ RiskIssue          │              │
│  │ version              │  ├────────────────────┤              │
│  └──────────────────────┤  │ id (PK)            │              │
│         │               │  │ title (UQ)         │              │
│         │               │  │ inherent_risk_score│              │
│  ┌──────▼──────────────┐│  └────────────────────┘              │
│  │ ExceptionCheckpoint ││                                       │
│  ├─────────────────────┤│  ┌────────────────────┐              │
│  │ id (PK)             ││  │ AssetType          │              │
│  │ exception_request_id├┤  ├────────────────────┤              │
│  │ checkpoint (enum)   ││  │ id (PK)            │              │
│  │ status (enum)       ││  │ name (UQ)          │              │
│  │ completed_by_id (FK)││  │ weight (1-8)       │              │
│  │ completed_at        ││  └────────────────────┘              │
│  │ notes               ││                                       │
│  └─────────────────────┘│  ┌──────────────────────┐            │
│                         │  │ AssetPurpose         │            │
│  ┌──────────────────────┤  ├──────────────────────┤            │
│  │ AuditLog             │  │ id (PK)              │            │
│  ├──────────────────────┤  │ name (UQ)            │            │
│  │ id (PK)              │  │ weight               │            │
│  │ exception_request_id ├─→│ └──────────────────────┤            │
│  │ action_type (enum)   │                                       │
│  │ previous_status      │  ┌──────────────────────┐            │
│  │ new_status           │  │ DataClassification   │            │
│  │ performed_by_id (FK) │  ├──────────────────────┤            │
│  │ timestamp (indexed)  │  │ id (PK)              │            │
│  │ details (JSON)       │  │ level (UQ)           │            │
│  └──────────────────────┤  │ weight               │            │
│                         │  └──────────────────────┘            │
│  ┌──────────────────────┤                                       │
│  │ ReminderLog          │  ┌──────────────────────┐            │
│  ├──────────────────────┤  │ DataComponent        │            │
│  │ id (PK)              │  ├──────────────────────┤            │
│  │ exception_request_id ├─→│ id (PK)              │            │
│  │ sent_to_id (FK)      │  │ name (UQ)            │            │
│  │ channel (email/sms)  │  │ weight               │            │
│  │ reminder_type        │  └──────────────────────┘            │
│  │ delivery_status      │                                       │
│  │ sent_at              │  ┌──────────────────────┐            │
│  │ message_content      │  │ InternetExposure     │            │
│  │ error_message        │  ├──────────────────────┤            │
│  └──────────────────────┘  │ id (PK)              │            │
│                            │ label (UQ)           │            │
│  ┌──────────────────────┐  │ weight               │            │
│  │ (M2M Junction Table) │  └──────────────────────┘            │
│  │ ExceptionRequest_    │                                       │
│  │ data_components      │  (Links exceptions to data           │
│  ├──────────────────────┤   components; multiple per exc.)     │
│  │ exceptionrequest_id  │                                       │
│  │ datacomponent_id     │                                       │
│  └──────────────────────┘                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Table Descriptions

### `exceptions_exceptionrequest`
**Purpose:** Core workflow entity tracking approval status, timeline, risk assessment.

| Field | Type | Nullable | Indexed | Purpose |
|-------|------|----------|---------|---------|
| `id` | BigInt | NO | YES | Primary key |
| `status` | Varchar(30) | NO | YES | Current approval stage (enum) |
| `business_unit_id` | BigInt | NO | NO | FK to BusinessUnit |
| `exception_type_id` | BigInt | NO | NO | FK to ExceptionType |
| `risk_issue_id` | BigInt | NO | NO | FK to RiskIssue |
| `requested_by_id` | Int | NO | NO | FK to User (requestor) |
| `assigned_approver_id` | Int | NO | NO | FK to User (BU CIO) |
| `risk_owner_id` | Int | NO | NO | FK to User (risk assessor) |
| `assigned_risk_owner_id` | Int | YES | NO | FK to User (sometimes nullable) |
| `short_description` | Text | NO | NO | Exception title/summary |
| `reason_for_exception` | Text | NO | NO | Business justification |
| `compensatory_controls` | Text | YES | NO | Mitigating controls if any |
| `approval_deadline` | Timestamp | YES | YES | SLA deadline (created_at + SLA days) |
| `approved_at` | Timestamp | YES | NO | When exception was approved |
| `exception_end_date` | Timestamp | YES | YES | Validity expiry date |
| `risk_score` | Int | YES | NO | Calculated risk (weighted product) |
| `risk_rating` | Varchar(20) | YES | NO | Low/Medium/High/Critical |
| `reminder_stage` | Varchar(50) | NO | NO | Reminder progress enum |
| `last_reminder_sent` | Timestamp | YES | NO | Last reminder timestamp |
| `asset_type_id` | BigInt | NO | NO | FK to AssetType |
| `asset_purpose_id` | BigInt | NO | NO | FK to AssetPurpose |
| `data_classification_id` | BigInt | NO | NO | FK to DataClassification |
| `internet_exposure_id` | BigInt | NO | NO | FK to InternetExposure |
| `number_of_assets` | Int | NO | NO | Count of affected assets |
| `created_at` | Timestamp | NO | YES | Auto-set on creation |
| `updated_at` | Timestamp | NO | NO | Auto-updated on change |
| `version` | Int | NO | NO | Optimistic locking counter |

**Key Constraints:**
- `status` enum only: Draft, Submitted, AwaitingRiskOwner, Approved, Rejected, Expired, Closed
- `number_of_assets >= 1`
- `approval_deadline` set only after Submitted
- `approved_at` set only after Approved
- `risk_score` calculated from risk engine
- `reminder_stage` progresses: None → Reminder_50 → Reminder_75 → Reminder_90 → Expired_Notice

---

### `exceptions_businessunit`
**Purpose:** Organizational unit responsible for exceptions; maps to CIO approver.

| Field | Type | Nullable | Unique |
|-------|------|----------|--------|
| `id` | BigInt | NO | - |
| `name` | Varchar(255) | NO | YES |
| `bu_code` | Varchar(50) | NO | YES |
| `cio_id` | Int | YES | NO |

**Example Data:**
```
Finance, FIN, cio_id=2
Operations, OPS, cio_id=3
IT, IT, cio_id=4
```

---

### `exceptions_exceptiontype`
**Purpose:** Exception category with approval SLA.

| Field | Type |
|-------|------|
| `id` | BigInt |
| `name` | Varchar(255) unique |
| `description` | Text |
| `approval_sla_days` | Int (default: 28) |

**Example Data:**
```
Firewall Exception, "Non-standard firewall rule", 28
Database Access Exception, "Elevated DB privileges", 21
Network Bypass, "Temporary network deviation", 14
```

---

### `exceptions_auditlog`
**Purpose:** Immutable record of all status changes, approvals, rejections.

| Field | Type | Indexed |
|-------|------|---------|
| `id` | BigInt | - |
| `exception_request_id` | BigInt | YES |
| `action_type` | Varchar(50) | NO |
| `previous_status` | Varchar(30) | NO |
| `new_status` | Varchar(30) | NO |
| `performed_by_id` | Int | NO |
| `timestamp` | Timestamp | YES |
| `details` | JSON | NO |

**Action Types:** SUBMIT, APPROVE, REJECT, CLOSE, UPDATE, ESCALATE

---

### `exceptions_exceptioncheckpoint`
**Purpose:** Workflow stage tracking (exception_requested, bu_approval_notified, final_decision, etc.).

| Field | Type |
|-------|------|
| `id` | BigInt |
| `exception_request_id` | BigInt |
| `checkpoint` | Varchar(100) |
| `status` | Varchar(50) enum (pending/completed/skipped/escalated) |
| `completed_at` | Timestamp nullable |
| `completed_by_id` | Int nullable |
| `notes` | Text |

---

### `exceptions_reminderlog`
**Purpose:** Deliverability tracking for notification campaigns.

| Field | Type |
|-------|------|
| `id` | BigInt |
| `exception_request_id` | BigInt |
| `sent_to_id` | Int |
| `channel` | Varchar(50) (email/sms) |
| `reminder_type` | Varchar(50) |
| `delivery_status` | Varchar(50) (sent/failed/bounced) |
| `sent_at` | Timestamp |
| `message_content` | Text (first 500 chars) |
| `error_message` | Text nullable |

---

## Risk Scoring Weights (Master Data)

All weights stored in reference tables; used by risk engine to calculate `risk_score`.

```
Risk Score = AssetType.weight × AssetPurpose.weight × DataClassification.weight × 
             InternetExposure.weight × (sum of DataComponent.weight)
```

**Risk Rating Thresholds (auto-determined):**
- `0–35`: Low
- `36–431`: Medium
- `432–1199`: High
- `≥1200`: Critical

---

## Data Population Layers

### Layer 1: Master Data
**When to seed:** On every fresh environment (dev, test, staging, prod)  
**Script:** `python manage.py seed_master_data`  
**Contents:**
- AssetType (Server, Workstation, Cloud, etc.)
- AssetPurpose (Database, Finance, etc.)
- DataClassification (Public, Confidential, Restricted, etc.)
- DataComponent (Customer DB, Employee Data, etc.)
- InternetExposure (Yes/No accessible from internet)

### Layer 2: Organization Data
**When to seed:** On every fresh environment  
**Script:** `python manage.py seed_org_data [--password PASS]`  
**Contents:**
- Groups (Requestor, Approver, RiskOwner, Security)
- Demo users (req_user, bu_approver, risk_owner, sec_user)

### Layer 3: Reference Data
**When to seed:** Once per environment for demo/testing  
**Script:** `python manage.py seed_extended_data [--force]`  
**Contents:**
- BusinessUnits (Finance, Operations, IT, etc.)
- ExceptionTypes (Firewall Exception, Database Access, etc.)
- RiskIssues (Firewall Rule Deviation, etc.)

### Layer 4: Synthetic Transactional Data
**When to seed:** For load testing / workflow validation only  
**Script:** `python manage.py seed_workflows [--count 20]`  
**Contents:**
- ExceptionRequests at various stages
- Sample approvals/rejections/escalations

---

## Migration Workflow

### Applying Migrations
```bash
# Show pending migrations
python manage.py showmigrations

# Apply all pending migrations
python manage.py migrate

# Apply specific app migrations
python manage.py migrate exceptions

# Apply up to specific migration
python manage.py migrate exceptions 0004
```

### Creating New Migrations
```bash
# Auto-detect model changes and create migration
python manage.py makemigrations exceptions --name descriptive_name

# Example:
python manage.py makemigrations exceptions --name add_approval_deadline_index
```

### Reversible Migrations (Testing)
```bash
# Reverse one migration
python manage.py migrate exceptions 0006

# Reverse all
python manage.py migrate exceptions zero

# Then re-apply all
python manage.py migrate exceptions
```

### Migration Rules (Frozen After v1.0)
1. **Allowed:** Add nullable columns, add indexes, add enum values, add constraints.
2. **Not allowed:** Rename columns, remove columns, alter NOT NULL constraints, alter primary keys.
3. **Before committing:** Test on fresh env (`migrate zero` → `migrate` → `seed_master_data` → run workflows).

---

## Backup & Restore

### Backup
```bash
# Full database dump
pg_dump -U postgres -h localhost grc_exceptions > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
pg_dump -U postgres -h localhost grc_exceptions | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore
```bash
# From SQL file
psql -U postgres -h localhost grc_exceptions < backup_20260327_120000.sql

# From compressed
gunzip backup_20260327_120000.sql.gz && psql -U postgres -h localhost grc_exceptions < backup_20260327_120000.sql
```

---

## Validation Checklist

- [ ] All migrations applied: `python manage.py showmigrations` (all show `[X]`)
- [ ] Schema matches models: `python manage.py inspectdb` (no unexpected schema drifts)
- [ ] Master data seeded: Run `seed_master_data`, check counts
- [ ] Org data seeded: Run `seed_org_data`, verify demo users
- [ ] Extended reference data seeded: Run `seed_extended_data`, verify BUs/exception types/risk issues
- [ ] Workflow test: Create/submit/approve/close one exception end-to-end
- [ ] Scheduler test: Run `python manage.py evaluate_pending_approvals`, verify reminders sent
- [ ] Backups work: Backup and restore to fresh DB
- [ ] No orphaned FK constraints: Check for data with missing foreign keys

---

## Support & Troubleshooting

### DB Connection Issues
```bash
# Test connection
psycopg2 -h localhost -U postgres -d grc_exceptions -c "SELECT 1"
```

### Check Current Schema
```bash
# From psql
\dt                          # List all tables
\d exceptions_exceptionrequest  # Show table structure
\i backend/schema.sql        # Load schema dump
```

### Reset DB (Development Only)
```bash
# Drop and recreate
python manage.py migrate exceptions zero
python manage.py migrate exceptions
python manage.py seed_master_data
python manage.py seed_org_data
python manage.py seed_extended_data
```

### Performance Issues
```bash
# Check slow queries (PostgreSQL log)
SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;

# Reindex all tables
REINDEX DATABASE grc_exceptions;
```

---

## Contact & Ownership

- **Database Schema Owner:** You (Intern)
- **Mentor/Technical Lead:** [Name]
- **Last Schema Review:** March 27, 2026

For questions, contact or escalate via team channel.
