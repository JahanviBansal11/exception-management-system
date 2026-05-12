# feat/expired-exceptions — Exception Expiry Lifecycle

**Branch base:** main (based on feat/modification-extension after merge)
**Purpose:** Full lifecycle when an approved exception's end date passes — auto-expiry, notification, remediation, and post-grace escalation.

---

## Epic 1: Auto-Expiry on End Date

### US-1: System marks Approved exceptions as Expired [DONE]

**As a** system (Celery Beat),
**I want** to automatically transition `Approved` exceptions to `Expired` when `exception_end_date` passes,
**So that** the system accurately reflects the real-world status of each exception.

**Acceptance Criteria:**
- [x] Hourly Celery Beat task `expire_active_exceptions` queries `Approved` exceptions where `exception_end_date < now`
- [x] Each is transitioned via `WorkflowService.mark_active_expired()` → `Expired`
- [x] `EXPIRE` audit log entry created with `"Exception end date passed — pending extension or remediation."`
- [x] `APPROVAL_ALLOWED_TRANSITIONS["Approved"]` includes `"Expired"`
- [x] `APPROVAL_ALLOWED_TRANSITIONS["Expired"]` allows `["Extended", "Closed"]`

**Files changed:** `models/exception_request.py`, `services/workflow_service.py`, `services/escalation_engine.py`, `tasks.py`, `grc_backend/celery.py`

---

### US-2: System notifies requestor and Security on expiry [DONE]

**As a** requestor / Security team member,
**I want** to receive an email when my exception expires,
**So that** I can take action (extend or remediate) within the 14-day grace window.

**Acceptance Criteria:**
- [x] `NotificationService.send_exception_expired_notification()` fires after `Approved → Expired`
- [x] Recipients: requestor email + all active `Security` group member emails (deduplicated)
- [x] Email body: exception ID, description, risk rating, expired-on date, BU, 14-day grace window warning, action link

**Files changed:** `services/notification_service.py`

---

## Epic 2: Post-Expiry Lifecycle

### US-3a: Requestor/Security can remediate and close an Expired exception [DONE]

**As a** requestor or Security team member,
**I want** to document remediation steps and close an expired exception,
**So that** the GRC record reflects the risk has been addressed without an extension.

**Acceptance Criteria:**
- [x] `POST /api/exceptions/{id}/remediate/` accepts `{ notes }` (mandatory, min 1 char)
- [x] Permission: requestor or Security only; status must be `Expired`
- [x] Transitions `Expired → Closed` via `WorkflowService.remediate(exception, user, notes)`
- [x] Audit log: action `CLOSE`, details contain `remediation_notes` key
- [x] `APPROVAL_ALLOWED_TRANSITIONS["Expired"]` already allows `"Closed"`
- [x] Frontend: "Remediate & Close" block visible for Expired exceptions to requestor/Security
- [x] Frontend: textarea for remediation notes; button disabled if empty; shows loading/error state

**Files changed:** `services/workflow_service.py`, `views/exception_views.py`, `DashboardPage.jsx`

---

### US-3b: Risk owner notified when 14-day grace window passes with no action [DONE]

**As a** risk owner,
**I want** to be notified when an Expired exception's 14-day grace window closes with no extension or remediation,
**So that** I can follow up and ensure the underlying risk is addressed.

**Acceptance Criteria:**
- [x] Hourly task `notify_unresolved_expired_exceptions` queries `Expired` exceptions where `exception_end_date + 14 days < now`
- [x] Skips any exception that already has a `ReminderLog(reminder_type="Overdue_Expired_Notice", delivery_status="sent")`
- [x] High/Critical risk → `[URGENT ACTION REQUIRED]` subject + urgent email template to risk owner
- [x] Low/Medium risk → `[ACTION REQUIRED]` subject + standard email template to risk owner
- [x] Creates `ReminderLog(reminder_type="Overdue_Expired_Notice")` after send attempt to prevent re-notification
- [x] `Overdue_Expired_Notice` added to `REMINDER_STAGE_CHOICES` (migration 0017)

**Files changed:** `models/exception_request.py`, `services/notification_service.py`, `services/escalation_engine.py`, `tasks.py`, `grc_backend/celery.py`

---

### US-3c: Worklist notification shows correct title for active expiry [DONE]

**As a** requestor,
**I want** the notification feed to show "Exception expired" (not "Approval deadline passed") when my active exception's end date passes,
**So that** I understand the type of expiry and the correct action to take.

**Acceptance Criteria:**
- [x] `EXPIRE` audit log with `new_status="Expired"` → title "Exception expired", severity "warning", message mentions 14-day grace window
- [x] `EXPIRE` audit log with `new_status="ApprovalDeadlinePassed"` → title "Approval deadline passed", severity "danger" (existing behaviour preserved)
- [x] Notification message for active expiry includes grace window reminder

**Files changed:** `views/worklist_views.py`

---

## Definition of Done

- [x] All ACs above checked off
- [x] Backend starts clean: `python manage.py check` → no errors
- [x] Migration 0017 applied: `python manage.py migrate`
- [ ] No regressions in existing workflow (submit → approve → reject → extend → modify paths) — manual QA pending
- [ ] Frontend renders Remediate & Close section for Expired exceptions (requestor/Security only) — manual QA pending
- [ ] Frontend renders "Exception expired" notification for active expiry events — manual QA pending

---

## Status Transition Map (reference)

```
Draft         → Submitted
Submitted     → AwaitingRiskOwner | Approved | Rejected | ApprovalDeadlinePassed
AwaitingRisk  → Approved | Rejected | ApprovalDeadlinePassed
Approved      → Closed | Extended | Expired          ← hourly: expire_active_exceptions
Rejected      → Closed | Modified
ApprovalDeadlinePassed → Draft
Expired       → Extended (14-day grace) | Closed (remediation)   ← THIS BRANCH
Modified      → (terminal)
Extended      → (terminal)
Closed        → (terminal)
```

## Celery Beat Tasks (this branch adds/renames)

| Task name | Schedule | What it does |
|---|---|---|
| `evaluate_pending_approvals` | every 5 min | Approval window reminders (50/75/90%) |
| `evaluate_active_exceptions` | every 10 min | Active exception expiry reminders |
| `escalate_expired_approvals` | hourly | ApprovalDeadlinePassed auto-transition |
| `expire_active_exceptions` | hourly | Approved → Expired when end date passes ← NEW |
| `notify_unresolved_expired_exceptions` | hourly | Notify risk owner after 14-day grace ← NEW |
