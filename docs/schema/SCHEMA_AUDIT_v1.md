# Schema Audit & Optimization Report
**Date:** March 27, 2026  
**Status:** PRE-FREEZE VALIDATION  
**Analyst:** Schema Review

---

## Executive Summary
Current schema is **70% production-ready**. Core workflow logic is sound, but missing constraints and optimizations will cause data quality issues and performance degradation under load. Estimated remediation: **2–3 days**.

---

## CRITICAL GAPS (Must Fix Before Freeze)

### 1. Missing Data Validation Constraints
**Impact:** High | **Severity:** Production blocker

| Field | Issue | Fix |
|-------|-------|-----|
| `ExceptionRequest.risk_rating` | CharField with no choices constraint | Add `choices=['Low', 'Medium', 'High', 'Critical']` |
| `ExceptionRequest.number_of_assets` | IntegerField, no min validation | Add `CheckConstraint(Q(number_of_assets__gte=1))` |
| `ExceptionRequest.risk_score` | IntegerField, no min validation | Add `CheckConstraint(Q(risk_score__gte=0))` |
| `ExceptionRequest.short_description` | TextField, no min length | Change to `CharField(max_length=500)` with validation |

**Action:** Create migration `0008_add_field_constraints.py`

---

### 2. Inconsistent Foreign Key ON_DELETE Behavior
**Impact:** Medium | **Severity:** Data integrity risk

**Current State:**
```
assigned_approver: ForeignKey(User, on_delete=models.PROTECT)  ← Prevents user deletion
risk_owner: ForeignKey(User, on_delete=models.PROTECT)         ← Prevents user deletion
assigned_risk_owner: ForeignKey(User, on_delete=models.SET_NULL, null=True)  ← Allows deletion
requested_by: ForeignKey(User, on_delete=models.PROTECT)       ← Prevents deletion
```

**Risk:** If `assigned_approver` or `risk_owner` user is deactivated, exception cannot be archived. `assigned_risk_owner=NULL` creates orphaned state.

**Fix:**
- Change `assigned_approver` and `risk_owner` to `SET_NULL` if users can be deactivated
- OR document that user lifecycle requires "deactivate, don't delete" policy
- **Recommended:** Keep PROTECT but add deactivation (is_active=False) pattern instead of deletion

**Action:** Add user lifecycle documentation + migration for soft-delete pattern

---

### 3. Missing Index on Scheduler Query Pattern
**Impact:** Medium | **Severity:** Performance degradation

Scheduler queries like:
```python
ExceptionRequest.objects.filter(
    status__in=['Submitted', 'AwaitingRiskOwner'],
    approval_deadline__lt=now,
    reminder_stage__in=['Reminder_90', 'Expired_Notice']
)
```

**Current Indexes:**
- `status` ✓
- `approval_deadline` ✓
- `reminder_stage` ✗ (missing)
- Compound `(status, approval_deadline)` ✗ (missing)

**Fix:**
```python
# In ExceptionRequest.Meta.indexes:
models.Index(fields=['status', 'approval_deadline']),  # Composite for scheduler
models.Index(fields=['reminder_stage']),               # For state filtering
models.Index(fields=['status', 'exception_end_date']), # For active exception close job
```

**Action:** Create migration `0009_add_scheduler_indexes.py`

---

### 4. N+1 Query Risk in ExceptionRequestSerializer
**Impact:** Medium | **Severity:** Performance under load

**Current:**
```python
# views.py line 724 (get_visible_exceptions_for_user)
visible = ExceptionRequest.objects.exclude(status="Draft")

# serializers.py returns:
checkpoints = CheckpointSerializer(many=True, read_only=True)  # N+1 for each exception

# views likely iterates without prefetch_related
```

**Fix:** Add to `ExceptionRequestViewSet.get_queryset()`:
```python
def get_queryset(self):
    visible, _ = get_visible_exceptions_for_user(self.request.user)
    return visible.prefetch_related(
        'checkpoints',
        'audit_logs',
        'reminder_logs',
        'data_components',
        'business_unit__cio',
        'exception_type',
    )
```

**Action:** Update [backend/exceptions/views.py](backend/exceptions/views.py) ViewSet

---

### 5. Missing Unique Constraint on Reminder Stage Progression
**Impact:** Low | **Severity:** Data quality

**Issue:** `ReminderEngine._get_reminder_type()` relies on string comparison logic, but DB allows:
```
- Reminder_50
- Reminder_75
- Reminder_90
- None (default)
```

But can have duplicate rows with same stage. Add:
```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['exception_request', 'reminder_stage'],
            condition=Q(reminder_stage__in=['Reminder_50', 'Reminder_75', 'Reminder_90']),
            name='unique_reminder_stage_per_exception',
        )
    ]
```

**Action:** Minor; add in next migration round

---

## OPTIMIZATION OPPORTUNITIES (Should Fix Before Freeze)

### 1. Index on BusinessUnit Queries
**Current:** No explicit index on `business_unit_id`  
**Fix:** ForeignKey auto-indexes, but add to frequently filtered queries:
```python
models.Index(fields=['business_unit', 'status']),
```

### 2. Rename `created_at` + `updated_at` to ISO Standard
**Current:** Standard Django pattern ✓ OK  
**Recommendation:** Keep as-is (industry standard)

### 3. Add Composite Index for Worklist Summary Queries
**Current:** Worklist summary does:
```python
my_queue.filter(status__in=["Submitted", "AwaitingRiskOwner"]).count()
my_queue.filter(status="Approved").count()  # Multiple status filters
```

**Fix:**
```python
models.Index(fields=['assigned_approver', 'status']),  # ✓ exists
models.Index(fields=['created_at', 'status']),         # ✓ exists
```
**Status:** Already optimized ✓

### 4. Denormalization: Cache Approver Name in AuditLog
**Current:** AuditLog.performed_by is FK, requires join to get name  
**Recommendation:** Keep as-is; queries are infrequent (audit read-only)

### 5. Risk Score Calculation Caching
**Current:** Recalculates on every `bu_approve()`  
**Recommendation:** Cache in DB field + validate on change (already done ✓)

### 6. Checkpoint Status Denormalization
**Current:** Checkpoint.status is separate model  
**Recommendation:** Keep as-is; clean separation of concerns

### 7. Consider JSON Field for Audit Details
**Current:** Uses `JSONField` for `AuditLog.details` ✓ Good  
**Recommendation:** Maintain; allows flexible audit logging

---

## Schema Freeze Checklist

- [ ] **[MUST] Fix 5 Critical Gaps** (see above)
  - [ ] Add risk_rating choices constraint
  - [ ] Add number_of_assets >= 1 constraint
  - [ ] Add risk_score >= 0 constraint
  - [ ] Document user lifecycle (PROTECT vs deactivation)
  - [ ] Add scheduler indexes

- [ ] **[SHOULD] Add Optimizations**
  - [ ] Add prefetch_related to ViewSet
  - [ ] Add composite (status, approval_deadline) index
  - [ ] Document index strategy

- [ ] **[NICE-TO-HAVE]** Post-Freeze
  - [ ] Add slow-query monitoring
  - [ ] Add query plan documentation
  - [ ] Benchmark under 100+ concurrent users

---

## Referendum: Freeze-Ready?

**Current:** ⚠️ NOT READY  
**With 5 Critical Fixes:** ✅ READY  
**Timeline:** 2–3 days to fix + test

**Recommended Action:**
1. Run migrations for constraints (30 min)
2. Run migrations for indexes (30 min)
3. Update ViewSet prefetch (15 min)
4. Run full test suite (30 min)
5. Run migrations once more on clean DB (1 hour)
6. **Then freeze**

