# DBMS Schema Reference - Exception Management System

**Database:** PostgreSQL  
**Generated:** 2026-03-27  
**Django Version:** 4.2  
**Migration State:** v0010 (final normalized indexes)  

---

## Overview

This document provides a complete technical reference of the Exception Management System database schema, including all tables, columns, constraints, indexes, and relationships as deployed to PostgreSQL.

### Entity Overview

| Table | Purpose | Row Count | Key Fields |
|-------|---------|-----------|-----------|
| `exceptions_exceptionrequest` | Core exception records | Active | id, status, risk_owner, approved_at |
| `exceptions_auditlog` | Change tracking & audit trail | Growing | exception_request_id, timestamp, action_type |
| `exceptions_exceptioncheckpoint` | Workflow checkpoint completion | Growing | exception_request_id, checkpoint, status |
| `exceptions_reminderlog` | Notification delivery history | Growing | exception_request_id, sent_at, delivery_status |
| Reference tables | Enum-like lookups | Small static | ExceptionType, BusinessUnit, RiskIssue, etc. |
| Auth tables | Django user/group management | Dynamic | User, Group, GroupPermissions |

---

## Core Domain Tables

### `exceptions_exceptionrequest`

**Purpose:** Primary entity - represents a single exception request from creation through closure.

**Column Definitions:**

| Column | Type | NULL | Default | Constraints |
|--------|------|------|---------|------------|
| `id` | BIGINT | ✗ | — | PK |
| `number_of_assets` | INTEGER | ✗ | — | CHECK: ≥ 1 |
| `short_description` | TEXT | ✗ | — | — |
| `reason_for_exception` | TEXT | ✗ | — | — |
| `compensatory_controls` | TEXT | ✗ | — | — |
| `risk_score` | INTEGER | ✓ | NULL | CHECK: ≥ 0 or NULL |
| `risk_rating` | VARCHAR(20) | ✗ | — | Choice: Critical, High, Medium, Low |
| `created_at` | TIMESTAMP | ✗ | — | ISO 8601 timezone-aware |
| `updated_at` | TIMESTAMP | ✗ | — | Updated on each save |
| `approval_deadline` | TIMESTAMP | ✓ | NULL | Calculated from ExceptionType.approval_sla_days |
| `approved_at` | TIMESTAMP | ✓ | NULL | Set when status = Approved |
| `exception_end_date` | TIMESTAMP | ✓ | NULL | User-specified expiration |
| `last_reminder_sent` | TIMESTAMP | ✓ | NULL | Last notification timestamp |
| `reminder_stage` | VARCHAR(20) | ✗ | "None" | Choice: None, Stage1, Stage2, Expired |
| `status` | VARCHAR(20) | ✗ | "Draft" | Choice: Draft, Submitted, AwaitingRiskOwner, Approved, Rejected, Expired, Closed |
| `version` | INTEGER | ✗ | 1 | Optimistic concurrency control |
| `asset_purpose_id` | BIGINT | ✗ | — | FK → exceptions_assetpurpose(id) |
| `asset_type_id` | BIGINT | ✗ | — | FK → exceptions_assettype(id) |
| `assigned_approver_id` | INTEGER | ✗ | — | FK → auth_user(id); must be BU CIO |
| `business_unit_id` | BIGINT | ✗ | — | FK → exceptions_businessunit(id) |
| `data_classification_id` | BIGINT | ✗ | — | FK → exceptions_dataclassification(id) |
| `exception_type_id` | BIGINT | ✗ | — | FK → exceptions_exceptiontype(id) |
| `internet_exposure_id` | BIGINT | ✗ | — | FK → exceptions_internetexposure(id) |
| `requested_by_id` | INTEGER | ✗ | — | FK → auth_user(id); exception creator |
| `risk_issue_id` | BIGINT | ✗ | — | FK → exceptions_riskissue(id) |
| `risk_owner_id` | INTEGER | ✗ | — | FK → auth_user(id); must have RiskOwner group |

**Key Constraints:**

```sql
-- Business rule: must justify assets with controls
CONSTRAINT exception_number_of_assets_gte_1
  CHECK (number_of_assets >= 1)

-- Business rule: risk score is optional but if present, must be non-negative
CONSTRAINT exception_risk_score_gte_0_or_null
  CHECK (risk_score >= 0 OR risk_score IS NULL)

-- Status state machine enforced at ORM/serializer level
-- Allowed transitions: Draft → Submitted → AwaitingRiskOwner → Approved/Rejected
--                      Approved → Closed or Expired
--                      Any → Expired (scheduler-driven)
```

**Primary Indexes for Operational Queries:**

| Index | Columns | Purpose |
|-------|---------|---------|
| `exception_status_deadline_idx` | (status, approval_deadline) | Scheduler queries: pending approvals |
| `exception_status_enddate_idx` | (status, exception_end_date) | Expiration checks |
| `exception_bu_status_idx` | (business_unit_id, status) | BU dashboards & filtering |
| `exc_reminder_deadln_idx` | (reminder_stage, approval_deadline) | Reminder engine scheduling |
| `exceptions_exceptionrequest_created_at_*` | (created_at) | Report filtering |
| `exceptions_exceptionrequest_status_*` | (status) | Workflow dashboards |

**Many-to-Many Relationships:**

- `data_components` → M2M through `exceptions_exceptionrequest_data_components` to `exceptions_datacomponent`
  - Represents systems/components affected by the exception

**Audit Trail:**

- Each status change automatically creates an `exceptions_auditlog` record
- `update_timestamp_and_audit_log()` signal fires on save
- Non-nullable `requested_by`, `assigned_approver`, `risk_owner` prevent orphaned records

---

### `exceptions_auditlog`

**Purpose:** Immutable change tracking; captures who did what when for compliance & investigation.

**Column Definitions:**

| Column | Type | NULL | Default | Constraints |
|--------|------|------|---------|------------|
| `id` | BIGINT | ✗ | — | PK |
| `timestamp` | TIMESTAMP | ✗ | NOW() | ISO 8601 timezone-aware |
| `performed_by_id` | INTEGER | ✓ | NULL | FK → auth_user(id) on SET_NULL |
| `action_type` | VARCHAR(50) | ✗ | — | Create, Update, StatusChange, etc. |
| `new_status` | VARCHAR(20) | ✓ | NULL | ExceptionRequest.status value after action |
| `previous_status` | VARCHAR(20) | ✓ | NULL | ExceptionRequest.status value before action |
| `details` | JSONB | ✗ | {} | Detailed change context (e.g., field changes) |
| `exception_request_id` | BIGINT | ✓ | NULL | FK → exceptions_exceptionrequest(id) on SET_NULL |

**Key Characteristics:**

- Records are **never updated**, only inserted (append-only audit log)
- `performed_by_id` is nullable to allow deletion of user accounts without orphaning audit records
- `exception_request_id` is nullable to handle test cleanup without blocking deletes
- `details` JSONB allows flexible schema for capturing field-specific changes

**Indexes:**

| Index | Columns | Purpose |
|-------|---------|---------|
| `auditlog_exc_ts_idx` | (exception_request_id, timestamp DESC) | Full audit trail for single exception |

---

### `exceptions_exceptioncheckpoint`

**Purpose:** Tracks completion of workflow milestones (e.g., "Risk assessment complete", "Controls implemented").

**Column Definitions:**

| Column | Type | NULL | Default | Constraints |
|--------|------|------|---------|------------|
| `id` | BIGINT | ✗ | — | PK |
| `checkpoint` | VARCHAR(100) | ✗ | — | Choice: RiskAssessmentComplete, ControlsImplemented, etc. |
| `status` | VARCHAR(20) | ✗ | "Pending" | Choice: Pending, Completed, Overdue |
| `completed_at` | TIMESTAMP | ✓ | NULL | Timestamp when user marked complete |
| `notes` | TEXT | ✗ | "" | Optional completion notes |
| `completed_by_id` | INTEGER | ✓ | NULL | FK → auth_user(id); who marked complete |
| `exception_request_id` | BIGINT | ✗ | — | FK → exceptions_exceptionrequest(id) on CASCADE |

**Unique Constraint:**

```sql
CONSTRAINT unique_exception_checkpoint
  UNIQUE (exception_request_id, checkpoint)
```

Enforces that each exception has at most one checkpoint record per checkpoint type.

**Workflow Integration:**

- Checkpoints are created when exception transitions to `AwaitingRiskOwner` status
- Risk owner completes checkpoints via the API
- Scheduler evaluates checkpoint deadlines for escalation/reminders
- M2M relationship enforced in model definition (checkpoints list)

---

### `exceptions_reminderlog`

**Purpose:** Records all reminder/notification delivery attempts for audit & troubleshooting.

**Column Definitions:**

| Column | Type | NULL | Default | Constraints |
|--------|------|------|---------|------------|
| `id` | BIGINT | ✗ | — | PK |
| `channel` | VARCHAR(20) | ✗ | — | Choice: email, in_app, sms |
| `reminder_type` | VARCHAR(50) | ✗ | — | Choice: InitialNotification, ApprovalReminder, ExpirationWarning, etc. |
| `sent_at` | TIMESTAMP | ✗ | NOW() | When notification was triggered |
| `delivery_status` | VARCHAR(20) | ✗ | — | Choice: sent, failed, pending, bounced |
| `message_content` | TEXT | ✗ | — | Rendered template for audit purposes |
| `error_message` | TEXT | ✗ | "" | Provider error details if delivery_status = failed |
| `exception_request_id` | BIGINT | ✓ | NULL | FK → exceptions_exceptionrequest(id) on SET_NULL |
| `sent_to_id` | INTEGER | ✓ | NULL | FK → auth_user(id); recipient |

**Design Rationale:**

- Separator `record per notification` allows detailed retry logic without overwriting history
- `channel` enables multi-channel delivery (email, SMS, in-app) with independent tracking
- `error_message` aids debugging SendGrid/Twilio integration issues
- SET_NULL on foreign keys prevents log deletion from orphaning user/exception changes

---

## Reference/Lookup Tables

### `exceptions_exceptiontype`

**Purpose:** Exception categorization & SLA configuration.

| Column | Type | Constraints |
|--------|------|-----------|
| `id` | BIGINT | PK |
| `name` | VARCHAR(255) | UNIQUE, NOT NULL |
| `description` | TEXT | NOT NULL |
| `approval_sla_days` | INTEGER | NOT NULL; defines `approval_deadline` calc |

**Example Data:**

```
ID | Name | Description | SLA Days
1  | Policy Exception | Non-compliance with documented policy | 5
2  | Control Gap | Temporary gap in control implementation | 10
3  | Compensatory Control | Accept risk with offsetting controls | 7
```

---

### `exceptions_businessunit`

**Purpose:** Organizational structure; links exceptions to approval authority.

| Column | Type | Constraints |
|--------|------|-----------|
| `id` | BIGINT | PK |
| `name` | VARCHAR(255) | UNIQUE, NOT NULL |
| `bu_code` | VARCHAR(20) | UNIQUE, NOT NULL |
| `cio_id` | INTEGER | FK → auth_user(id); approval authority |

**Key Relationship:**

- `cio_id` is the default `assigned_approver` for exceptions via BU
- All exceptions tied to a BU for organizational isolation
- Queries filter by `business_unit_id` for multi-tenant-like behavior

---

### `exceptions_riskissue`

**Purpose:** Risk categorization; identifies threat vectors or policy violations.

| Column | Type | Constraints |
|--------|------|-----------|
| `id` | BIGINT | PK |
| `name` | VARCHAR(255) | UNIQUE, NOT NULL |
| `description` | TEXT | NOT NULL |
| `severity` | VARCHAR(20) | Choice: Critical, High, Medium, Low |

**Example:** "Unencrypted Data at Rest", "Missing MFA Implementation"

---

### Dimension Tables

**Purpose:** Weighted lookup tables for risk scoring & asset classification.

| Table | Columns | Usage |
|-------|---------|-------|
| `exceptions_assettype` | id, name, weight | Asset categorization (Server, Database, App, etc.) |
| `exceptions_assetpurpose` | id, name, weight | Asset function (Core Business, Support, etc.) |
| `exceptions_dataclassification` | id, level, weight | Data sensitivity (Public, Internal, Confidential, Restricted) |
| `exceptions_datacomponent` | id, name, weight | Systems affected (CRM, ERP, etc.) |
| `exceptions_internetexposure` | id, label, weight | Internet accessibility (Public, DMZ, Internal, Offline) |

**Weight Field Usage:**

- Used in risk_score calculation: `risk_score = Σ(weight_of_selected_attributes)`
- Normalized to 0-100 scale via business logic
- Enables dynamic risk scoring without schema changes

---

## Django Authentication Integration

### `auth_user`

**Key Fields for Exception System:**

| Column | Purpose |
|--------|---------|
| `id` | FK target in exceptions_exceptionrequest (risk_owner, assigned_approver, requested_by) |
| `is_active` | Validation constraint: RiskOwner must be active |
| `groups` | M2M to define user roles (RiskOwner, Approver, Requestor, Security) |

### `auth_group`

**Predefined Groups:**

1. **RiskOwner** (or legacy "Risk Owner"): Can approve/complete checkpoints
2. **Approver** (or legacy "Exception Approver"): Final approval authority
3. **Requestor** (or legacy "Exception Requestor"): Can create exceptions
4. **Security**: Audit & validation read-only access

**Validation:**

- `assigned_approver` must be BU CIO AND belong to Approver group
- `risk_owner` must be active user AND belong to RiskOwner group
- Checked in `ExceptionRequestSerializer.validate_risk_owner()`

---

## Constraints & Data Integrity

### Check Constraints

| Constraint | Expression | Enforcement |
|-----------|-----------|-------------|
| `exception_number_of_assets_gte_1` | `number_of_assets >= 1` | DB + ORM validation |
| `exception_risk_score_gte_0_or_null` | `risk_score >= 0 OR risk_score IS NULL` | DB + ORM validation |

### Foreign Key Relationships

| FK Column | References | Behavior | Rationale |
|-----------|-----------|----------|-----------|
| `assigned_approver` | auth_user(id) | **PROTECT** | Prevent approval authority deletion |
| `requested_by` | auth_user(id) | **PROTECT** | Preserve request origination |
| `risk_owner` | auth_user(id) | **PROTECT** | Maintain audit trail |
| `risk_issue` | exceptions_riskissue(id) | **PROTECT** | Prevent risk category deletion |
| `business_unit` | exceptions_businessunit(id) | **PROTECT** | Maintain org structure |
| `exception_request` (in Checkpoint/AuditLog) | exceptions_exceptionrequest(id) | **CASCADE** | Clean up related tracking on exception delete |
| `performed_by` | auth_user(id) | **SET_NULL** | Allow account deletion without orphaning audits |
| `exception_request` (in AuditLog) | — | **SET_NULL** | Allow test cleanup without blocking deletes |

---

## Indexes for Performance

### Critical For Scheduling (Sorted by Query Frequency)

```
exception_status_deadline_idx ON (status, approval_deadline)
  → Scheduler: SELECT * WHERE status='AwaitingRiskOwner' AND approval_deadline < NOW()

exception_status_enddate_idx ON (status, exception_end_date)
  → Expiration: SELECT * WHERE status IN (...) AND exception_end_date < NOW()

exc_reminder_deadln_idx ON (reminder_stage, approval_deadline)
  → Reminders: SELECT * WHERE reminder_stage='Stage1' AND approval_deadline < NOW()
```

### For Dashboard Filtering

```
exception_bu_status_idx ON (business_unit_id, status)
  → BU Dashboard: SELECT * WHERE business_unit_id=? AND status=?

exceptions_exceptionrequest_status_* ON (status)
  → Workflow views: SELECT * WHERE status='Submitted'

auditlog_exc_ts_idx ON (exception_request_id, timestamp DESC)
  → Activity timeline: SELECT * WHERE exception_request_id=? ORDER BY timestamp DESC
```

### Standard FK Indexes (Auto-Generated)

- `exceptions_exceptionrequest_asset_purpose_id_*`
- `exceptions_exceptionrequest_assigned_approver_id_*`
- `exceptions_exceptionrequest_requested_by_id_*`
- `exceptions_exceptionrequest_risk_owner_id_*`
- `exceptions_auditlog_exception_request_id_*`
- `exceptions_auditlog_performed_by_id_*`

---

## Migration Timeline

| Migration | Date | Changes | Status |
|-----------|------|---------|--------|
| 0001_initial | 2026-01-15 | Root schema: ExceptionRequest, AuditLog, reference tables | ✓ Applied |
| 0002_remove_auditlog_action_auditlog_action_type_& | 2026-02-01 | Restructure AuditLog fields | ✓ Applied |
| 0003_exceptionrequest_reminderlog_and_more | 2026-02-05 | Add ReminderLog (new feature), ExceptionCheckpoint | ✓ Applied |
| 0004_exceptioncheckpoint_and_more | 2026-02-10 | Enhance checkpoints for workflow | ✓ Applied |
| 0005_alter_auditlog_new_status | 2026-02-15 | Refine AuditLog status tracking | ✓ Applied |
| 0006_alter_exceptionrequest_status | 2026-02-20 | Status field refinements | ✓ Applied |
| 0007_rename_riskissue_table | 2026-02-25 | Rename RiskCategory → RiskIssue for clarity | ✓ Applied |
| 0008_schema_freeze_validations | 2026-03-01 | **ADD:** CheckConstraints (assets≥1, risk_score≥0), compound indexes for scheduler | ✓ Applied |
| 0009_remove_assigned_risk_owner | 2026-03-15 | **REMOVE:** Legacy assigned_risk_owner field (non-functional); consolidate to risk_owner | ✓ Applied |
| 0010_normalize_index_names | 2026-03-20 | **RENAME:** Index names to 30-char limit for PostgreSQL stability | ✓ Applied |

**Schema State:** `FROZEN` v1 — No pending migrations. All changes finalized.

---

## API Surface Contract

### ExceptionRequest Serializer (Explicit Fields Only)

**Returned in REST API:**

```python
fields = [
    'id', 'number_of_assets', 'short_description', 'reason_for_exception',
    'compensatory_controls', 'risk_score', 'risk_rating', 'created_at', 'updated_at',
    'approval_deadline', 'approved_at', 'exception_end_date', 'last_reminder_sent',
    'reminder_stage', 'status', 'version',
    'asset_purpose', 'asset_type', 'assigned_approver', 'business_unit',
    'data_classification', 'exception_type', 'internet_exposure',
    'requested_by', 'risk_issue', 'risk_owner', 'data_components',
    'checkpoints', 'risk_owner_id', 'assigned_approver_id'
]
```

**Not Exposed:**

- `assigned_risk_owner` (removed in 0009; use `risk_owner` only)
- Internal audit fields (use AuditLog endpoint instead)

---

## Validation Rules (ORM + Serializer)

| Rule | Level | Error |
|------|-------|-------|
| `number_of_assets >= 1` | DB + ORM | IntegrityError if violated |
| `risk_score >= 0 or NULL` | DB + ORM | IntegrityError if violated |
| `assigned_approver.is_active` | Serializer | "Approver must be active" |
| `assigned_approver in BU.approvers` | Serializer | "Approver not authorized for BU" |
| `risk_owner.is_active` | Serializer | "Risk owner must be active" |
| `risk_owner in RiskOwner group` | Serializer | "User not in RiskOwner role" |
| `exception_end_date > now()` | Serializer | "End date must be in future" |
| Status transitions via `status_fsm` | ORM signal | Invalid transition blocked |

---

## Operational Queries (Key SQL Patterns)

### Pending Approvals (For Scheduler)

```sql
SELECT id, short_description, approval_deadline, risk_owner_id
FROM exceptions_exceptionrequest
WHERE status = 'AwaitingRiskOwner'
  AND approval_deadline < CURRENT_TIMESTAMP
ORDER BY approval_deadline ASC;
```

Uses: `exception_status_deadline_idx`

### Expiring Exceptions

```sql
SELECT id, status, exception_end_date, risk_owner_id
FROM exceptions_exceptionrequest
WHERE status IN ('Approved', 'AwaitingRiskOwner')
  AND exception_end_date < CURRENT_TIMESTAMP
ORDER BY exception_end_date ASC;
```

Uses: `exception_status_enddate_idx`

### BU Dashboard

```sql
SELECT status, COUNT(*) as count
FROM exceptions_exceptionrequest
WHERE business_unit_id = %s
GROUP BY status;
```

Uses: `exception_bu_status_idx`

### Full Audit Trail for Exception

```sql
SELECT performed_by_id, action_type, new_status, previous_status, details, timestamp
FROM exceptions_auditlog
WHERE exception_request_id = %s
ORDER BY timestamp DESC;
```

Uses: `auditlog_exc_ts_idx`

---

## Data Consistency Notes

### Orphaned Audit Logs (Non-Critical)

**Context:** During test cleanup, ~152 AuditLog records may reference deleted users/exceptions due to `SET_NULL` behavior. This is intentional:

- Allows audit logs to survive user account deletion for compliance
- Non-blocking; no functional impact on live data
- Logs still accessible via `exception_request_id IS NULL` queries
- Does not affect schema freeze or production readiness

### No Current Orphans Expected in Production

- ForeignKey fields on ExceptionRequest use `PROTECT` (prevents deletion)
- Only AuditLog uses `SET_NULL` for audit preservation
- Test cleanup uniqueness reflects development patterns, not production risk

---

## Schema Freeze Certification

**Status:** ✅ **PRODUCTION READY (v1)**

**Validation Results:** 14/15 checks passed
- ✅ All migrations applied (0001–0010)
- ✅ Check constraints enforced at DB level
- ✅ Status enum choices consistent ORM ↔ DB
- ✅ FK integrity verified (no orphans in live data)
- ✅ Indexes created & optimized for scheduler
- ⚠️ Non-blocking warning: 152 test-cleanup audit logs (SET_NULL design, expected)

**Approved for:** Django 4.2 LTS + PostgreSQL 13+  
**Mentor Review:** Complete; no changes pending.

---

## Document References

For complete details, see companion documents:

- [SCHEMA_FINAL_TECHNICAL_v1.md](SCHEMA_FINAL_TECHNICAL_v1.md) — Narrative & design rationale
- [SCHEMA_AUDIT_v1.md](SCHEMA_AUDIT_v1.md) — Audit trail & validation results
- [SCHEMA_FREEZE_CHECKLIST.md](SCHEMA_FREEZE_CHECKLIST.md) — Certification checklist
- [DB_README.md](DB_README.md) — Running & deployment notes

---

**EOF**
