# Schema v1 Freeze Checklist

**Freeze Date:** March 27, 2026  
**Target Lock Date:** April 10, 2026 (end of Week 2)  
**Purpose:** Establish canonical data model; no structural changes without P0 bug fix approval

---

## Core Tables (Must Exist & Be Correct)

### Reference/Master Data (immutable)
- [ ] `exceptions_businessunit` — BU code, name, CIO assignment
- [ ] `exceptions_exceptiontype` — type name, approval SLA days
- [ ] `exceptions_riskissue` — title, inherent risk score
- [ ] `exceptions_assettype` — name, weight
- [ ] `exceptions_assetpurpose` — name, weight
- [ ] `exceptions_dataclassification` — level, weight
- [ ] `exceptions_datacomponent` — name, weight
- [ ] `exceptions_internetexposure` — label, weight

### Core Business Table
- [ ] `exceptions_exceptionrequest` — all required fields present and indexed

**Required fields in ExceptionRequest:**
- [ ] `id` (auto PK)
- [ ] `status` (CharField, choices only: Draft/Submitted/AwaitingRiskOwner/Approved/Rejected/Expired/Closed)
- [ ] `business_unit_id` (FK, NOT NULL)
- [ ] `exception_type_id` (FK, NOT NULL)
- [ ] `risk_issue_id` (FK, NOT NULL)
- [ ] `requested_by_id` (FK, NOT NULL)
- [ ] `assigned_approver_id` (FK, NOT NULL)
- [ ] `risk_owner_id` (FK, NOT NULL)
- [ ] `approval_deadline` (DateTime, indexed, nullable)
- [ ] `exception_end_date` (DateTime, indexed, nullable)
- [ ] `created_at` (DateTime, auto_now_add, indexed)
- [ ] `updated_at` (DateTime, auto_now)
- [ ] `risk_score` (Int, nullable)
- [ ] `risk_rating` (Char, nullable)
- [ ] `reminder_stage` (CharField, choices only)
- [ ] `version` (Int, default 0)

### Audit & Workflow
- [ ] `exceptions_auditlog` — action_type, previous/new status, timestamp, performed_by
- [ ] `exceptions_reminderlog` — sent_to, reminder_type, delivery_status, message_content
- [ ] `exceptions_exceptioncheckpoint` — checkpoint status, completed_by, notes

### Many-to-Many
- [ ] `exceptions_exceptionrequest_data_components` (junction table)

---

## Constraints & Indexes (Must Be Present)

### Constraints
- [ ] Check: `risk_issue.inherent_risk_score >= 0`
- [ ] Check: `exceptionrequest.number_of_assets >= 1`
- [ ] Unique: `businessunit.bu_code`
- [ ] Unique: `exceptiontype.name`
- [ ] Unique: `riskissue.title`

### Indexes (Performance)
- [ ] `exceptionrequest(status)` — CRITICAL for dashboard filters
- [ ] `exceptionrequest(approval_deadline)` — CRITICAL for scheduler
- [ ] `exceptionrequest(exception_end_date)` — CRITICAL for scheduler
- [ ] `exceptionrequest(created_at)` — dashboard sorting
- [ ] `exceptionrequest(requested_by, status)` — requestor queue
- [ ] `exceptionrequest(assigned_approver, status)` — approver queue
- [ ] `auditlog(exception_request_id, action_type)` — audit history
- [ ] `auditlog(timestamp)` — audit timeline searches

---

## Enum/Status Values (Locked)

### ExceptionRequest Status (immutable)
```
Draft
Submitted
AwaitingRiskOwner
Approved
Rejected
Expired
Closed
```

### Reminder Stages (immutable)
```
None
Reminder_50
Reminder_75
Reminder_90
Expired_Notice
```

### Checkpoint Status (immutable)
```
pending
completed
skipped
escalated
```

---

## Sign-Off

**Schema reviewed by:**  
- [ ] Developer (you): ________________  
- [ ] Mentor/Tech Lead: ________________  

**Date:** ________________

---

## Post-Freeze Rules

1. **No structural changes** (add/remove/rename columns) without mentor + ticket approval.
2. **Only allowed changes:**
   - Add nullable columns (requires migration)
   - Add new enum values (document in migration)
   - Add indexes (requires migration)
   - Drop unused indexes ONLY if blocking performance
3. **Migration must:**
   - Have a clear docstring explaining the reason
   - Be reversible (reverse() method)
   - Include data validation/cleanup if data-affecting
4. **All migrations tested** before merge (fresh DB + seed + workflow test).

---

## Next Steps After Freeze

- **Week 3:** Final seed script validation; populate demo BU/users/risk data.
- **Week 4:** Clean environment test (fresh migrate + seed + full workflow).
- **Week 5–6:** UAT with stakeholders; log schema feedback but defer to v1.1.
- **Month 3:** Lock schema v1.1 based on UAT findings; create final seed + backup playbook.
