# SQL Quick Reference Guide

Common operational queries for the Exception Management System database.

---

## Approval & Scheduler Queries

### Find Pending Approvals (Next 48 Hours)

```sql
SELECT 
  id, 
  short_description, 
  approval_deadline,
  risk_owner_id,
  assigned_approver_id,
  business_unit_id
FROM exceptions_exceptionrequest
WHERE status = 'AwaitingRiskOwner'
  AND approval_deadline < CURRENT_TIMESTAMP + INTERVAL '2 days'
ORDER BY approval_deadline ASC;
```

**Used by:** Scheduler, dashboard escalation warnings  
**Index:** `exception_status_deadline_idx` (status, approval_deadline)

---

### Find Overdue Approvals (Past Deadline)

```sql
SELECT 
  id, 
  short_description,
  approval_deadline,
  risk_owner_id,
  assigned_approver_id,
  CURRENT_TIMESTAMP - approval_deadline AS overdue_by
FROM exceptions_exceptionrequest
WHERE status = 'AwaitingRiskOwner'
  AND approval_deadline < CURRENT_TIMESTAMP
ORDER BY approval_deadline ASC;
```

**Use Case:** Escalation, management reporting  
**Expected result:** None in normal operation (scheduler prevents)

---

### Find Expiring Exceptions

```sql
SELECT 
  id,
  short_description,
  status,
  exception_end_date,
  approved_at,
  CURRENT_TIMESTAMP - exception_end_date AS days_expired
FROM exceptions_exceptionrequest
WHERE (status = 'Approved' OR status = 'AwaitingRiskOwner')
  AND exception_end_date < CURRENT_TIMESTAMP
ORDER BY exception_end_date ASC;
```

**Used by:** Daily scheduler job  
**Index:** `exception_status_enddate_idx` (status, exception_end_date)

---

### Find Reminders to Send (Next Wave)

```sql
-- Stage 1 Reminders (5 days before deadline)
SELECT 
  id,
  short_description,
  risk_owner_id,
  assigned_approver_id,
  approval_deadline,
  CURRENT_TIMESTAMP + INTERVAL '5 days' AS stage1_threshold
FROM exceptions_exceptionrequest
WHERE reminder_stage = 'None'
  AND approval_deadline BETWEEN CURRENT_TIMESTAMP AND CURRENT_TIMESTAMP + INTERVAL '5 days'
ORDER BY approval_deadline ASC;

-- Stage 2 Reminders (1 day before deadline, urgent)
SELECT
  id,
  short_description,
  risk_owner_id,
  assigned_approver_id,
  approval_deadline
FROM exceptions_exceptionrequest
WHERE reminder_stage = 'Stage1'
  AND approval_deadline BETWEEN CURRENT_TIMESTAMP AND CURRENT_TIMESTAMP + INTERVAL '1 day'
ORDER BY approval_deadline ASC;
```

**Used by:** reminder_engine.py (scheduler)  
**Index:** `exc_reminder_deadln_idx` (reminder_stage, approval_deadline)

---

## Business Unit & Dashboard Queries

### Exception Count By Status (BU Dashboard)

```sql
SELECT 
  status,
  COUNT(*) as count
FROM exceptions_exceptionrequest
WHERE business_unit_id = %s
  AND status != 'Closed'
GROUP BY status
ORDER BY status;
```

**Result Example:**
```
Status              | Count
──────────────────┼──────
Draft               │    2
Submitted           │    5
AwaitingRiskOwner   │   12
Approved            │    8
Rejected            │    1
Expired             │    3
```

**Used by:** BU dashboard, KPI reporting  
**Index:** `exception_bu_status_idx` (business_unit_id, status)

---

### Exceptions by Business Unit & Created Date

```sql
SELECT 
  bu.name as business_unit,
  DATE(er.created_at) as created_date,
  COUNT(*) as count,
  SUM(CASE WHEN er.status = 'Approved' THEN 1 ELSE 0 END) as approved,
  SUM(CASE WHEN er.status = 'Rejected' THEN 1 ELSE 0 END) as rejected
FROM exceptions_exceptionrequest er
JOIN exceptions_businessunit bu ON er.business_unit_id = bu.id
WHERE er.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY bu.name, DATE(er.created_at)
ORDER BY bu.name, created_date DESC;
```

**Used by:** Monthly reporting, trend analysis

---

## Audit & Compliance Queries

### Full Change History for Single Exception

```sql
SELECT 
  timestamp,
  performed_by_id,
  au.username,
  action_type,
  previous_status,
  new_status,
  details
FROM exceptions_auditlog al
LEFT JOIN auth_user au ON al.performed_by_id = au.id
WHERE al.exception_request_id = %s
ORDER BY timestamp DESC;
```

**Used by:** Audit trail UI, compliance verification  
**Index:** `auditlog_exc_ts_idx` (exception_request_id, timestamp DESC)

---

### Status Change Audit Trail

```sql
SELECT 
  er.id,
  er.short_description,
  al.timestamp,
  al.previous_status,
  al.new_status,
  au.username as changed_by
FROM exceptions_auditlog al
JOIN exceptions_exceptionrequest er ON al.exception_request_id = er.id
LEFT JOIN auth_user au ON al.performed_by_id = au.id
WHERE al.action_type = 'StatusChange'
  AND al.new_status IN ('Approved', 'Rejected', 'Expired')
  AND al.timestamp >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY al.timestamp DESC;
```

**Used by:** Compliance audit, SLA verification

---

### Who Made Changes (User Activity)

```sql
SELECT 
  au.username,
  COUNT(*) as changes_made,
  MIN(al.timestamp) as first_change,
  MAX(al.timestamp) as last_change
FROM exceptions_auditlog al
LEFT JOIN auth_user au ON al.performed_by_id = au.id
WHERE al.timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY au.username
ORDER BY changes_made DESC;
```

**Used by:** User activity tracking, security audit

---

## Risk & Assessment Queries

### High Risk Exceptions (Approved but not Closed)

```sql
SELECT 
  id,
  short_description,
  risk_rating,
  risk_score,
  status,
  approved_at,
  exception_end_date,
  EXTRACT(DAYS FROM exception_end_date - CURRENT_TIMESTAMP) AS days_remaining
FROM exceptions_exceptionrequest
WHERE (risk_rating = 'Critical' OR risk_rating = 'High')
  AND status IN ('Approved', 'AwaitingRiskOwner')
ORDER BY risk_score DESC;
```

**Used by:** Risk dashboard, escalation monitoring  
**Index:** Status index helps filter

---

### Risk Score Distribution

```sql
SELECT 
  risk_rating,
  COUNT(*) as count,
  AVG(risk_score) as avg_score,
  MIN(risk_score) as min_score,
  MAX(risk_score) as max_score
FROM exceptions_exceptionrequest
WHERE status IN ('Approved', 'AwaitingRiskOwner')
GROUP BY risk_rating
ORDER BY risk_score DESC;
```

**Used by:** Risk analytics, trend reporting

---

## Data Quality & Maintenance Queries

### Find Orphaned Audit Logs (Non-Critical)

```sql
SELECT COUNT(*)
FROM exceptions_auditlog
WHERE exception_request_id IS NULL;
```

**Expected:** ~152 in dev (after test cleanup)  
**Production:** Should be 0 (PROTECT prevents deletion)

---

### Find Incomplete Checkpoints

```sql
SELECT 
  er.id,
  er.short_description,
  ec.checkpoint,
  ec.status,
  ec.created_at,
  EXTRACT(DAYS FROM CURRENT_TIMESTAMP - ec.created_at) AS days_pending
FROM exceptions_exceptioncheckpoint ec
JOIN exceptions_exceptionrequest er ON ec.exception_request_id = er.id
WHERE ec.status = 'Pending'
  AND er.status NOT IN ('Rejected', 'Expired', 'Closed')
ORDER BY er.approval_deadline ASC;
```

**Used by:** Workflow monitoring, escalations

---

### Reminder Delivery Status

```sql
SELECT 
  channel,
  reminder_type,
  delivery_status,
  COUNT(*) as count,
  COUNT(CASE WHEN delivery_status = 'failed' THEN 1 END) as failed_count
FROM exceptions_reminderlog
WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY channel, reminder_type, delivery_status
ORDER BY sent_at DESC;
```

**Used by:** Notification system monitoring, SendGrid integration debug

---

### Failed Reminder Resend Candidates

```sql
SELECT 
  rl.id,
  rl.exception_request_id,
  rl.sent_to_id,
  rl.channel,
  rl.error_message,
  rl.sent_at
FROM exceptions_reminderlog rl
WHERE rl.delivery_status = 'failed'
  AND rl.sent_at >= CURRENT_DATE - INTERVAL '3 days'
ORDER BY rl.sent_at DESC
LIMIT 20;
```

**Used by:** Support/remediation, notification troubleshooting

---

## User & Role Queries

### Risk Owners by Business Unit

```sql
SELECT 
  bu.name as business_unit,
  au.username,
  au.email,
  COUNT(er.id) as assigned_exceptions
FROM auth_user au
JOIN auth_user_groups aug ON au.id = aug.user_id
JOIN auth_group ag ON aug.group_id = ag.id
LEFT JOIN exceptions_exceptionrequest er ON au.id = er.risk_owner_id AND er.status != 'Closed'
CROSS JOIN (
  SELECT bu.id FROM exceptions_businessunit bu
) bu
WHERE ag.name IN ('RiskOwner', 'Risk Owner')
GROUP BY bu.name, au.username, au.email
ORDER BY bu.name, assigned_exceptions DESC;
```

**Used by:** Workload analysis, team management

---

### Users Missing Role Assignment

```sql
SELECT 
  au.id,
  au.username,
  au.email,
  au.is_active
FROM auth_user au
WHERE au.id NOT IN (
  SELECT user_id FROM auth_user_groups 
  WHERE group_id IN (
    SELECT id FROM auth_group 
    WHERE name IN ('RiskOwner', 'Approver', 'Requestor', 'Security',
                   'Risk Owner', 'Exception Approver', 'Exception Requestor')
  )
)
AND au.is_active = true
AND au.is_staff = false;
```

**Used by:** Audit, detection of mis-configured users

---

## Performance & Index Verification

### Check Index Usage

```sql
SELECT 
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND tablename LIKE 'exceptions_%'
ORDER BY idx_scan DESC;
```

**Used by:** Performance tuning, identifying unused indexes

---

### Check Table Bloat

```sql
SELECT 
  schemaname,
  tablename,
  round(100 * pg_relation_size(schemaname||'.'||tablename) / 
        pg_total_relation_size(schemaname||'.'||tablename), 2) AS table_bloat_ratio
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'exceptions_%'
ORDER BY pg_relation_size(schemaname||'.'||tablename) DESC;
```

**Used by:** Maintenance planning, VACUUM schedule

---

## Migration & Schema Verification

### List All Applied Migrations

```sql
SELECT 
  app,
  name,
  applied
FROM django_migrations
WHERE app = 'exceptions'
ORDER BY applied DESC;
```

**Expected Output:** 10 rows (0001–0010), all applied

---

### Verify Check Constraints

```sql
SELECT 
  constraint_name,
  table_name,
  constraint_definition
FROM information_schema.check_constraints
WHERE table_name LIKE 'exceptions_%'
ORDER BY table_name, constraint_name;
```

**Verify:**
- `exception_number_of_assets_gte_1` exists
- `exception_risk_score_gte_0_or_null` exists

---

### Verify Foreign Keys

```sql
SELECT 
  constraint_name,
  table_name,
  column_name,
  foreign_table_name,
  foreign_column_name
FROM information_schema.referential_constraints rc
JOIN information_schema.constraint_column_usage ccu 
  ON rc.constraint_name = ccu.constraint_name
JOIN information_schema.table_constraints tc 
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name LIKE 'exceptions_%'
ORDER BY tc.table_name, tc.constraint_name;
```

**Verify:** All expected FKs present (risk_owner, assigned_approver, etc.)

---

## Troubleshooting Queries

### Find Exceptions Stuck in Draft

```sql
SELECT 
  id,
  short_description,
  created_at,
  EXTRACT(DAYS FROM CURRENT_TIMESTAMP - created_at) AS days_in_draft
FROM exceptions_exceptionrequest
WHERE status = 'Draft'
  AND created_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY created_at ASC;
```

**Use Case:** Detect stalled requests, contact requestor

---

### Find Exceptions Missing Approval Deadline

```sql
SELECT 
  id,
  short_description,
  status,
  created_at,
  approval_deadline,
  exception_type_id
FROM exceptions_exceptionrequest
WHERE approval_deadline IS NULL
  AND status != 'Draft';
```

**Expected:** 0 rows (deadline set on submission)  
**Issue:** If > 0, scheduler may have issue

---

### Timeout & Lock Diagnostics

```sql
SELECT 
  pid,
  usename,
  state,
  query,
  state_change,
  wait_event
FROM pg_stat_activity
WHERE datname = 'current_database'
  AND state != 'idle'
ORDER BY state_change DESC;
```

**Use Case:** Debug slow queries, identify locks

---

## Backup & Recovery

### Full Schema Dump (Command Line)

```bash
pg_dump -U postgres -h localhost my_database > backup_$(date +%Y%m%d).sql
```

### Restore Schema

```bash
psql -U postgres -h localhost my_database < backup_20260327.sql
```

### Table-Level Backup

```bash
pg_dump -U postgres -h localhost -t exceptions_exceptionrequest \
  my_database > exceptionrequest_backup.sql
```

---

## Notes

- **All TIMESTAMP columns:** UTC, timezone-aware (Django migration default)
- **All queries:** Parameterized with `%s` placeholders (prevent SQL injection)
- **Performance:** Compound indexes optimize WHERE clauses with multiple conditions
- **Scheduler assumptions:** Runs every 5–15 min, must handle de-duplication
- **NULL handling:** Use `IS NULL` / `IS NOT NULL`, not `= NULL`

For full schema reference, see [DBMS_SCHEMA_REFERENCE.md](DBMS_SCHEMA_REFERENCE.md).
