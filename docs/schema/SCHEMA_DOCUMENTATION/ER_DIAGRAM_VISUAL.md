# Entity-Relationship Diagram

Visual representation of the Exception Management System schema relationships.

---

## ER Diagram (ASCII + Mermaid)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXCEPTION MANAGEMENT SYSTEM                         │
│                              DATA MODEL                                      │
└─────────────────────────────────────────────────────────────────────────────┘

                                [auth_user]
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
        (requested_by)      (assigned_approver)   (risk_owner)
                │                   │                   │
                ▼                   ▼                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │          exceptions_exceptionrequest (CORE ENTITY)           │
    ├──────────────────────────────────────────────────────────────┤
    │ PK: id (BIGINT)                                              │
    │ Status: Draft → Submitted → AwaitingRiskOwner →              │
    │         Approved/Rejected → Closed/Expired                   │
    │ Timestamps: created_at, updated_at, approval_deadline,       │
    │             approved_at, exception_end_date                  │
    │ Risk: risk_score (≥0 or NULL), risk_rating (Critical/High/..)│
    ├──────────────────────────────────────────────────────────────┤
    │ FK: business_unit_id → [exceptions_businessunit]             │
    │ FK: exception_type_id → [exceptions_exceptiontype]           │
    │ FK: risk_issue_id → [exceptions_riskissue]                   │
    │ FK: asset_type_id → [exceptions_assettype]                   │
    │ FK: asset_purpose_id → [exceptions_assetpurpose]             │
    │ FK: data_classification_id → [exceptions_dataclassification] │
    │ FK: internet_exposure_id → [exceptions_internetexposure]     │
    │ M2M: data_components ↔ [exceptions_datacomponent]            │
    └──────────────────────────────────────────────────────────────┘
        │           │           │
        │           │           │
        ├─ CASCADE ─┴─ CASCADE ──┤
        │                        │
        ▼                        ▼
    [exceptions_auditlog]    [exceptions_exceptioncheckpoint]
    (Change tracking)        (Workflow milestones)
    ├─────────────────────┐  ├────────────────────┐
    │ id (BIGINT)         │  │ id (BIGINT)        │
    │ timestamp (audit)   │  │ checkpoint (enum)  │
    │ performed_by_id ─┐  │  │ status (enum)      │
    │ action_type      │  │  │ completed_at       │
    │ new_status       │  │  │ completed_by_id ──┐│
    │ previous_status  │  │  │                   ││
    │ details (JSONB)  │  │  └────────────────────┘│
    └─────────────────────┘                        │
         ▲                                          │
         │                  ┌───────────────────────┘
         │                  │
    (performed_by/   (completed_by)
     SET_NULL)       (nullable)
         │                  │
         └──────────────────┴──→ [auth_user]


┌────────────────────────────────────┐
│   REFERENCE TABLES (Lookups)       │
├────────────────────────────────────┤
│ ├─ exceptions_businessunit         │
│ │  └─ [cio_id] → [auth_user]       │
│ │                                   │
│ ├─ exceptions_exceptiontype        │
│ │  └─ approval_sla_days (config)   │
│ │                                   │
│ ├─ exceptions_riskissue            │
│ │  └─ severity categorization      │
│ │                                   │
│ ├─ DIMENSIONAL LOOKUPS (weighted)  │
│ │  ├─ exceptions_assettype         │
│ │  ├─ exceptions_assetpurpose      │
│ │  ├─ exceptions_dataclassification│
│ │  ├─ exceptions_datacomponent     │
│ │  └─ exceptions_internetexposure  │
│ │                                   │
│ └─ exceptions_reminderlog          │
│    (Notification delivery history) │
│    ├─ channel (email|sms|in_app)   │
│    ├─ sent_to_id → [auth_user]     │
│    ├─ delivery_status (enum)       │
│    └─ exception_request_id (SET_NULL)│
└────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   DJANGO AUTHENTICATION (Framework)    │
├─────────────────────────────────────────┤
│ [auth_user]                             │
│  ├─ username, email, is_active, etc     │
│  └─ M2M groups (explicit role control)  │
│      ├─ RiskOwner                       │
│      ├─ Approver                        │
│      ├─ Requestor                       │
│      └─ Security                        │
└─────────────────────────────────────────┘
```

---

## Relationship Matrix

| From Table | To Table | Relationship | FK Behavior | Purpose |
|-----------|----------|--------------|------------|---------|
| ExceptionRequest | auth_user | N:1 (requested_by) | PROTECT | Track request originator |
| ExceptionRequest | auth_user | N:1 (assigned_approver) | PROTECT | Approval authority (BU CIO) |
| ExceptionRequest | auth_user | N:1 (risk_owner) | PROTECT | Risk assessment owner |
| ExceptionRequest | BusinessUnit | N:1 | PROTECT | Org isolation & CIO lookup |
| ExceptionRequest | ExceptionType | N:1 | PROTECT | SLA config & categorization |
| ExceptionRequest | RiskIssue | N:1 | PROTECT | Risk category tracking |
| ExceptionRequest | AssetType | N:1 | PROTECT | Asset class (for scoring) |
| ExceptionRequest | AssetPurpose | N:1 | PROTECT | Asset function (for scoring) |
| ExceptionRequest | DataClassification | N:1 | PROTECT | Data sensitivity (for scoring) |
| ExceptionRequest | InternetExposure | N:1 | PROTECT | Network exposure (for scoring) |
| ExceptionRequest | DataComponent | M:M | CASCADE | Systems affected (multi-select) |
| AuditLog | ExceptionRequest | N:1 | SET_NULL | Survive test cleanup |
| AuditLog | auth_user | N:1 | SET_NULL | Survive user deletion |
| ExceptionCheckpoint | ExceptionRequest | N:1 | CASCADE | Clean on exception delete |
| ExceptionCheckpoint | auth_user | N:1 | nullable | Workflow completion tracking |
| ReminderLog | ExceptionRequest | N:1 | SET_NULL | Notification audit trail |
| ReminderLog | auth_user | N:1 | nullable | Delivery recipient |
| BusinessUnit | auth_user | N:1 | nullable | BU CIO (approver) |

---

## Status State Machine

```
                    START
                      │
                      ▼
                   [Draft]
                      │
              (Requestor creates)
                      │
                      ▼
                [Submitted]
                      │
         (System validates, assigns Risk Owner)
                      │
                      ▼
           [AwaitingRiskOwner]
                      │
    ┌─────────────────┼──────────────────┐
    │                 │                  │
    │ (Risk owner      │ (Risk owner    │  (Scheduler)
    │  approves)       │  rejects)      │  
    │                 │                  │
    ▼                 ▼                  ▼
[Approved]        [Rejected]         [Expired]
    │                                    │
    │ (Workflow            (No recovery)│
    │  completes)                        │
    │                                    │
    └────────────┬─────────────────────┘
                 │
        (End date reached)
                 │
                 ▼
              [Closed/Expir]
                 │
            (Timeline end)
                 │
               [END]

KEY:
- Status is immutable once set (ORM constraint)
- Automatic transitions triggered by:
  * Scheduler (CronJob) for Expired
  * API endpoints for Submitted, Approved, Rejected, Closed
- Checkpoints created at AwaitingRiskOwner entry
- Reminders sent at specific stages (Stage1, Stage2)
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         REQUEST LIFECYCLE                                │
└──────────────────────────────────────────────────────────────────────────┘

1. CREATION
   ┌─────────────────────────────────────────────────────────────┐
   │ Requestor (API)                                             │
   │  └─ POST /exceptions/                                       │
   │     ├─ Assign to Business Unit + Risk Owner                │
   │     ├─ Set exception_end_date (future date)                │
   │     └─ Select: Type, Risk Issue, Asset Type, Classification│
   │                                                              │
   │ → ExceptionRequest created (Draft)                          │
   │ → AuditLog entry (CREATE action)                            │
   │ → ReminderLog entry may be created for initial notification│
   └─────────────────────────────────────────────────────────────┘

2. SUBMISSION
   ┌─────────────────────────────────────────────────────────────┐
   │ Requestor (API)                                             │
   │  └─ PATCH /exceptions/{id}/                                │
   │     └─ status: Draft → Submitted                            │
   │                                                              │
   │ → ExceptionRequest.status = Submitted                       │
   │ → AuditLog entry (StatusChange: Draft → Submitted)         │
   │ → System validates and auto-assigns Risk Owner             │
   └─────────────────────────────────────────────────────────────┘

3. RISK ASSESSMENT
   ┌─────────────────────────────────────────────────────────────┐
   │ System (Scheduler: every 5 min)                             │
   │  └─ SELECT * FROM exceptions_exceptionrequest               │
   │     WHERE status = 'Submitted'                              │
   │     ├─ Calculate risk_score from dimensions                │
   │     ├─ Assign Approval Authority (BU CIO)                  │
   │     ├─ Set approval_deadline from SLA                      │
   │     └─ Transition to AwaitingRiskOwner                     │
   │                                                              │
   │ → ExceptionRequest.status = AwaitingRiskOwner              │
   │ → ExceptionCheckpoint records created (Pending)            │
   │ → AuditLog entry (StatusChange: Submitted → ...)          │
   │ → ReminderLog entry (InitialNotification via email)        │
   └─────────────────────────────────────────────────────────────┘

4. RISK OWNER REVIEW
   ┌─────────────────────────────────────────────────────────────┐
   │ Risk Owner (API)                                            │
   │  └─ Completes checkpoints via PATCH /exceptions/{id}/      │
   │     checkpoint/{checkpoint_name}/                           │
   │     ├─ Mark checkpoint COMPLETED                           │
   │     ├─ Add notes (e.g., "Controls implemented on 2026-...")│
   │     └─ Set completed_by = self                             │
   │                                                              │
   │ → ExceptionCheckpoint.status = Completed                   │
   │ → ExceptionCheckpoint.completed_at = NOW                   │
   │ → AuditLog entry (action: CHECKPOINT_COMPLETE)             │
   └─────────────────────────────────────────────────────────────┘

5. APPROVAL / REJECTION
   ┌─────────────────────────────────────────────────────────────┐
   │ Assigned Approver (API)                                     │
   │  └─ PATCH /exceptions/{id}/                                │
   │     └─ status: AwaitingRiskOwner → Approved/Rejected       │
   │                                                              │
   │ IF APPROVED:                                                │
   │  → ExceptionRequest.status = Approved                      │
   │  → ExceptionRequest.approved_at = NOW                      │
   │  → AuditLog entry (StatusChange: AwaitingRiskOwner → App...)
   │  → Exception is now valid (workflow proceeds to closure)   │
   │                                                              │
   │ IF REJECTED:                                                │
   │  → ExceptionRequest.status = Rejected                      │
   │  → ExceptionRequest.approved_at = NULL                     │
   │  → AuditLog entry (StatusChange: AwaitingRiskOwner → Rej...)
   │  → Requestor can create new exception request              │
   └─────────────────────────────────────────────────────────────┘

6. EXPIRATION / CLOSURE
   ┌─────────────────────────────────────────────────────────────┐
   │ System (Scheduler: daily)                                   │
   │  └─ SELECT * FROM exceptions_exceptionrequest               │
   │     WHERE exception_end_date < NOW()                        │
   │                                                              │
   │ IF status = Approved:                                       │
   │  → Transition to Expired                                   │
   │  → ReminderLog entry (ExpirationWarning)                   │
   │  → AuditLog entry (StatusChange: Approved → Expired)       │
   │                                                              │
   │ IF status = AwaitingRiskOwner AND approval_deadline < NOW:│
   │  → Transition to Expired                                   │
   │  → ReminderLog entry (ApprovalDeadlineExceeded)            │
   │  → AuditLog entry (StatusChange: AwaitingRiskOwner → Exp..│
   │                                                              │
   │ User can manually close exception before end_date          │
   │  → Transition to Closed (via API)                          │
   │  → AuditLog entry (Manual closure)                         │
   └─────────────────────────────────────────────────────────────┘

7. AUDIT & REPORTING
   ┌─────────────────────────────────────────────────────────────┐
   │ Security Team (READ-ONLY API)                               │
   │  └─ GET /exceptions/{id}/audit-log/                        │
   │     └─ Full timeline of all changes, approvals, reminders  │
   │                                                              │
   │ → AuditLog queries show:                                    │
   │    - Who (performed_by) did what (action_type)             │
   │    - When (timestamp, ISO 8601)                            │
   │    - What changed (details, JSONB)                         │
   │    - Full status transition history (new/prev status)      │
   │                                                              │
   │ → Supports compliance, incident investigation, SLA tracking│
   └─────────────────────────────────────────────────────────────┘
```

---

## Reminder & Escalation Flow

```
Exception Created (Submitted)
        │
        ▼
    Decision: Is end_date set by requestor?
        │
     YES│  NO
        │  │
        ▼  ▼
    System calculates remainder_stage
        │
        ├─ More than 10 days until approval_deadline
        │  └─ reminder_stage = "None"
        │  └─ Next check: 5 days before
        │
        ├─ Between 5-10 days before deadline
        │  └─ reminder_stage = "Stage1"
        │  └─ ReminderLog: (channel=email, type=ApprovalReminder)
        │  └─ Next check: 1 day before
        │
        ├─ Less than 1 day before deadline
        │  └─ reminder_stage = "Stage2"  
        │  └─ ReminderLog: (channel=email+sms, type=UrgentApprovalReminder)
        │
        └─ Past deadline
           └─ reminder_stage = "Expired"
           └─ ReminderLog: (type=ExpirationWarning)
           └─ System auto-updates status → Expired

Scheduler triggers reminder_engine.py
    │
    ├─ Query: (reminder_stage='Stage1' AND approval_deadline < now()+5d)
    │  └─ Send email via SendGrid
    │  └─ Log: ReminderLog(channel='email', delivery_status='sent')
    │
    └─ Query: (reminder_stage='Stage2' AND approval_deadline < now()+1d)
       └─ Send email + SMS  
       └─ Log: ReminderLog(channel='email'/'sms', delivery_status='sent'/'failed')
```

---

## Index Strategy Visualization

```
SCHEDULER-CRITICAL (High Query Frequency)
═════════════════════════════════════════

exception_status_deadline_idx: (status, approval_deadline)
  ↓
  Scheduler query (every 5 min):
  SELECT * FROM exceptions_exceptionrequest
  WHERE status = 'AwaitingRiskOwner'
    AND approval_deadline < CURRENT_TIMESTAMP
  ORDER BY approval_deadline ASC
  └─ Returns pending approvals for escalation

exception_status_enddate_idx: (status, exception_end_date)
  ↓
  Expiration check (daily):
  SELECT * FROM exceptions_exceptionrequest
  WHERE status IN ('Submitted', 'Approved')
    AND exception_end_date < CURRENT_TIMESTAMP
  └─ Returns expired exceptions for auto-closure

exc_reminder_deadln_idx: (reminder_stage, approval_deadline)
  ↓
  Reminder scheduling (every 5 min):
  SELECT * FROM exceptions_exceptionrequest
  WHERE reminder_stage = 'Stage1'
    AND approval_deadline < CURRENT_TIMESTAMP + INTERVAL '5 days'
  └─ Returns cases due for reminder notifications


DASHBOARD & FILTERING (Medium Frequency)
═════════════════════════════════════════

exception_bu_status_idx: (business_unit_id, status)
  ↓
  BU dashboard:
  SELECT status, COUNT(*)
  FROM exceptions_exceptionrequest
  WHERE business_unit_id = %s
  GROUP BY status
  └─ Status breakdown by business unit

exceptions_exceptionrequest_status_*: (status)
  ↓
  Workflow views:
  SELECT COUNT(*)
  FROM exceptions_exceptionrequest
  WHERE status = 'Draft'
  └─ Totals per status


AUDIT TRAIL (Medium Frequency + Interactive)
═════════════════════════════════════════════

auditlog_exc_ts_idx: (exception_request_id, timestamp DESC)
  ↓
  Activity timeline:
  SELECT * FROM exceptions_auditlog
  WHERE exception_request_id = %s
  ORDER BY timestamp DESC
  LIMIT 100
  └─ Full change history for UI timeline view


STANDARD FK INDEXES (Automatic, Low Frequency)
═══════════════════════════════════════════════

Created automatically for all ForeignKey fields:
  - (asset_purpose_id)
  - (assigned_approver_id)
  - (risk_owner_id)
  - (business_unit_id)
  - etc.

Used for JOIN operations in nested serializers
Example:
  SELECT * FROM exceptions_exceptionrequest
  WHERE risk_owner_id = %s
```

---

## Constraint Enforcement Model

```
APPLICATION LAYER (Django ORM)
──────────────────────────────

ExceptionRequestSerializer
  └─ validate_risk_owner()
     ├─ Check: user.is_active
     ├─ Check: user in RiskOwner group
     └─ Raise ValidationError if fails

  └─ validate_exception_end_date()
     ├─ Check: date > now()
     └─ Raise ValidationError if fails

  └─ validate_assigned_approver()
     ├─ Check: assigned_approver == business_unit.cio
     ├─ Check: assigned_approver in Approver group
     └─ Raise ValidationError if fails

Models
  └─ clean() method (optional, called before save)
  └─ signals.py:update_timestamp_and_audit_log()
     └─ Auto-create AuditLog on every save


DATABASE LAYER (PostgreSQL)
───────────────────────────

CHECK Constraints (Enforced at INSERT/UPDATE)
  ├─ exception_number_of_assets_gte_1
  │  └─ number_of_assets >= 1
  │
  └─ exception_risk_score_gte_0_or_null
     └─ (risk_score >= 0 OR risk_score IS NULL)

FOREIGN KEY Constraints (Referential Integrity)
  ├─ assigned_approver_id → auth_user(id)
  │  └─ Action on delete: PROTECT
  │  └─ Effect: Cannot delete approver while assigned
  │
  ├─ risk_owner_id → auth_user(id)
  │  └─ Action on delete: PROTECT
  │  └─ Effect: Cannot delete risk owner while assigned
  │
  ├─ exception_request_id (in AuditLog) → exceptionrequest(id)
  │  └─ Action on delete: SET_NULL
  │  └─ Effect: Delete exception → orphaned (but immutable) audit logs
  │
  └─ Etc. (25+ foreign keys total)

PRIMARY KEY Constraints
  ├─ exceptions_exceptionrequest.id
  ├─ exceptions_auditlog.id
  └─ Etc. (uniqueness + fast lookup)

UNIQUE Constraints
  ├─ exceptions_businessunit(name)
  ├─ exceptions_businessunit(bu_code)
  ├─ exceptions_exceptiontype(name)
  └─ Prevents duplicate reference data


INTERACTION MODEL (Layered Defense)
───────────────────────────────────

ORM Validation              Database Constraints
       │                           │
       ├─ Pre-save checks         │
       │  ├─ Risk owner group     │
       │  ├─ Approver authority   │
       │  └─ End date future      │
       │                           │
       ▼                           ▼
   Save to DB          →     INSERT/UPDATE
   (serializer.save())        (constraint check)
                              │
                              ├─ CHECK violations → IntegrityError
                              ├─ FK violations → IntegrityError  
                              └─ UNIQUE violations → IntegrityError
                              │
                              ▼
                           Committed (or rolled back)
```

---

## Summary

This visual documentation complements the detailed DBMS reference:
- **ER Diagram** shows relationships, cardinality, FK behaviors
- **Relationship Matrix** lists all N:1, M:M connections
- **Status Machine** illustrates workflow transitions
- **Data Flow** depicts request lifecycle with system actions
- **Index Strategy** shows performance optimization points
- **Constraint Model** demonstrates layered data integrity

For full technical details, see [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md).
