# Final Schema Technical Specification (v1)

**Date:** March 27, 2026  
**System:** Exception Management System  
**Database:** PostgreSQL  
**App:** Django 4.2 + DRF

---

## 1) Scope

This document is the final technical schema handoff for mentor review. It captures:
- canonical entities and relationships,
- constrained fields and enums,
- performance indexes,
- migration state,
- validation and test evidence.

---

## 2) Canonical Core Entities

## `exceptions_exceptionrequest`
Primary workflow table for exception lifecycle.

### Key fields
- `id` (PK)
- `status` (enum-like choices in model)
- `business_unit_id` (FK, PROTECT)
- `exception_type_id` (FK, PROTECT)
- `risk_issue_id` (FK, PROTECT)
- `asset_type_id` (FK, PROTECT)
- `asset_purpose_id` (FK, PROTECT)
- `data_classification_id` (FK, PROTECT)
- `internet_exposure_id` (FK, PROTECT)
- `number_of_assets` (integer, validated)
- `short_description` (text)
- `reason_for_exception` (text)
- `compensatory_controls` (text, blank allowed)
- `risk_score` (int, nullable, validated)
- `risk_rating` (choices: `Low|Medium|High|Critical`)
- `created_at`, `updated_at`
- `approval_deadline` (nullable datetime)
- `approved_at` (nullable datetime)
- `exception_end_date` (nullable datetime)
- `last_reminder_sent` (nullable datetime)
- `reminder_stage` (choices: `None|Reminder_50|Reminder_75|Reminder_90|Expired_Notice`)
- `requested_by_id` (FK User, PROTECT)
- `assigned_approver_id` (FK User, PROTECT)
- `risk_owner_id` (FK User, PROTECT)
- `version` (optimistic locking)

### Removed redundant field
- `assigned_risk_owner_id` removed in migration `0009`.
- Canonical owner field is now **`risk_owner_id`** only.

## `exceptions_exceptioncheckpoint`
Workflow checkpoint state and notes (`pending|completed|skipped|escalated`).

## `exceptions_auditlog`
Immutable action history for transition and update tracking.

## `exceptions_reminderlog`
Reminder delivery audit and content marker storage.

## Reference tables
- `exceptions_businessunit`
- `exceptions_exceptiontype`
- `exceptions_riskissue`
- `exceptions_assettype`
- `exceptions_assetpurpose`
- `exceptions_dataclassification`
- `exceptions_datacomponent`
- `exceptions_internetexposure`

Junction table:
- `exceptions_exceptionrequest_data_components`

---

## 3) Data Integrity Rules

## DB constraints
- `exception_number_of_assets_gte_1`
- `exception_risk_score_gte_0_or_null`

## App-level validation (DRF serializer)
- `risk_owner` must be present.
- `risk_owner` must be active.
- `risk_owner` must belong to role group (`RiskOwner` or legacy `Risk Owner`).
- `assigned_approver` must match BU CIO on create.
- `exception_end_date` must be future.
- minimum text/number validations on key fields.

## Status transition matrix
- `Draft -> Submitted`
- `Submitted -> AwaitingRiskOwner|Approved|Rejected|Expired`
- `AwaitingRiskOwner -> Approved|Rejected|Expired`
- `Approved -> Closed`
- `Rejected -> Draft`
- `Expired -> Draft`
- `Closed -> (terminal)`

---

## 4) Indexing and Query Performance

Critical indexes currently present for scheduler and queues:
- `(status, approval_deadline)`
- `(status, exception_end_date)`
- `(reminder_stage, approval_deadline)`
- `(business_unit, status)`
- plus queue/sort indexes (`requested_by,status`, `assigned_approver,status`, `created_at,status`, etc.)

Notes:
- Existing index names in DB include both framework-generated and named indexes from prior migrations.
- Functionally correct; can be normalized in a non-breaking index hygiene migration later.

---

## 5) Migration State (Schema Milestones)

Applied sequence:
- `0001` to `0007` base and workflow migrations
- `0008_schema_freeze_validations` (constraints + scheduler indexes)
- `0009_...` (remove `assigned_risk_owner`, finalize field metadata)

---

## 6) Verification Evidence

Validated on March 27, 2026:
- `python manage.py check` ✅
- `python manage.py test exceptions.tests` ✅
- `python test_checkpoint_workflow.py` ✅
- `python schema_validation.py` ✅ (no errors)

---

## 7) Recommended Next Hardening (Post-Freeze, Non-Blocking)

1. Add one migration to normalize legacy/duplicate index names only.
2. Standardize role name to `RiskOwner` only and retire legacy `Risk Owner` compatibility.
3. Keep serializer field list explicit (already done) and avoid `__all__` for contract stability.

---

## 8) Sign-off

- Developer: ____________________
- Mentor/Reviewer: ____________________
- Date: ____________________
