"""
Schema Freeze Validation Script
Test all constraints, indexes, and data integrity rules before migration.

Usage:
  python schema_validation.py
"""

import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grc_backend.settings')
django.setup()

from django.db import connection
from django.db.models import Q
from django.contrib.auth.models import User
from exceptions.models import (
    ExceptionRequest, BusinessUnit, ExceptionType, RiskIssue,
    AssetType, AssetPurpose, DataClassification, DataComponent,
    InternetExposure, AuditLog, ExceptionCheckpoint, ReminderLog,
)

class SchemaValidator:
    """Validate schema constraints and data integrity."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []
    
    def log_pass(self, msg):
        self.passed.append(f"✓ {msg}")
        print(f"✓ {msg}")
    
    def log_warn(self, msg):
        self.warnings.append(f"⚠ {msg}")
        print(f"⚠ {msg}")
    
    def log_error(self, msg):
        self.errors.append(f"✗ {msg}")
        print(f"✗ {msg}")
    
    def validate_data_constraints(self):
        """Validate that existing data satisfies new constraints."""
        print("\n--- DATA CONSTRAINT VALIDATION ---")
        
        # 1. Check number_of_assets >= 1
        invalid_assets = ExceptionRequest.objects.filter(number_of_assets__lt=1).count()
        if invalid_assets > 0:
            self.log_error(f"{invalid_assets} exceptions have number_of_assets < 1")
        else:
            self.log_pass("All exceptions have number_of_assets >= 1")
        
        # 2. Check risk_score >= 0 or NULL
        invalid_scores = ExceptionRequest.objects.filter(
            risk_score__isnull=False,
            risk_score__lt=0
        ).count()
        if invalid_scores > 0:
            self.log_error(f"{invalid_scores} exceptions have negative risk_score")
        else:
            self.log_pass("All risk_scores are NULL or >= 0")
        
        # 3. Check risk_rating is valid choice
        valid_ratings = ['Low', 'Medium', 'High', 'Critical', '']
        invalid_ratings = ExceptionRequest.objects.exclude(
            risk_rating__in=valid_ratings
        ).count()
        if invalid_ratings > 0:
            self.log_error(f"{invalid_ratings} exceptions have invalid risk_rating")
        else:
            self.log_pass("All risk_ratings are valid (Low/Medium/High/Critical)")
    
    def validate_foreign_keys(self):
        """Validate foreign key integrity."""
        print("\n--- FOREIGN KEY VALIDATION ---")
        
        # 1. Orphaned assigned_approver
        orphaned_approver = ExceptionRequest.objects.filter(
            assigned_approver__isnull=True,
            status__in=['Submitted', 'Approved', 'AwaitingRiskOwner']
        ).count()
        if orphaned_approver > 0:
            self.log_warn(f"{orphaned_approver} active exceptions have NULL assigned_approver")
        else:
            self.log_pass("All active exceptions have assigned_approver")
        
        # 2. Orphaned risk_owner
        orphaned_risk_owner = ExceptionRequest.objects.filter(
            risk_owner__isnull=True,
            status__in=['Submitted', 'Approved', 'AwaitingRiskOwner']
        ).count()
        if orphaned_risk_owner > 0:
            self.log_warn(f"{orphaned_risk_owner} active exceptions have NULL risk_owner")
        else:
            self.log_pass("All active exceptions have risk_owner")
        
        # 3. requested_by integrity
        orphaned_requester = ExceptionRequest.objects.filter(
            requested_by__isnull=True
        ).count()
        if orphaned_requester > 0:
            self.log_error(f"{orphaned_requester} exceptions have NULL requested_by")
        else:
            self.log_pass("All exceptions have requested_by")
    
    def validate_indexes(self):
        """Check if critical indexes exist."""
        print("\n--- INDEX VALIDATION ---")
        
        # List all indexes on exceptions_exceptionrequest table
        cursor = connection.cursor()
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'exceptions_exceptionrequest'
            ORDER BY indexname;
        """)
        
        indexes = cursor.fetchall()
        index_names = [idx[0] for idx in indexes]
        
        required_indexes = [
            'exception_status_deadline_idx',  # (status, approval_deadline)
            'exception_status_enddate_idx',   # (status, exception_end_date)
            'exception_reminder_deadline_idx', # (reminder_stage, approval_deadline)
            'exception_bu_status_idx',        # (business_unit, status)
        ]
        
        for req_idx in required_indexes:
            if any(req_idx in idx for idx in index_names):
                self.log_pass(f"Index for {req_idx} exists")
            else:
                self.log_warn(f"Index for {req_idx} NOT YET created (will be in migration)")
    
    def validate_constraints(self):
        """Check database constraints."""
        print("\n--- CONSTRAINT VALIDATION ---")
        
        cursor = connection.cursor()
        cursor.execute("""
            SELECT conname
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'exceptions_exceptionrequest'
            AND c.contype = 'c'
            ORDER BY conname;
        """)
        
        constraints = cursor.fetchall()
        constraint_names = [c[0] for c in constraints]
        
        required_constraints = [
            'exception_number_of_assets_gte_1',
            'exception_risk_score_gte_0_or_null',
        ]
        
        for req_const in required_constraints:
            if any(req_const in c for c in constraint_names):
                self.log_pass(f"Constraint {req_const} exists")
            else:
                self.log_warn(f"Constraint {req_const} is missing")
    
    def validate_workflow_logic(self):
        """Validate workflow logic is sound."""
        print("\n--- WORKFLOW LOGIC VALIDATION ---")
        
        # Test valid status transitions
        test_statuses = {
            'Draft': ['Submitted'],
            'Submitted': ['AwaitingRiskOwner', 'Approved', 'Rejected', 'Expired'],
            'AwaitingRiskOwner': ['Approved', 'Rejected', 'Expired'],
            'Approved': ['Closed'],
            'Rejected': ['Draft'],
            'Expired': ['Draft'],
            'Closed': [],
        }
        
        allowed = ExceptionRequest.APPROVAL_ALLOWED_TRANSITIONS
        if allowed == test_statuses:
            self.log_pass("Status transition matrix is correct")
        else:
            self.log_error("Status transition matrix mismatch")
    
    def validate_referential_integrity(self):
        """Check for orphaned records."""
        print("\n--- REFERENTIAL INTEGRITY VALIDATION ---")
        
        # AuditLog references
        orphaned_audit = AuditLog.objects.filter(
            exception_request__isnull=True,
            performed_by__isnull=True
        ).count()
        if orphaned_audit > 0:
            self.log_warn(f"{orphaned_audit} audit logs without references")
        else:
            self.log_pass("All audit logs have valid references")
        
        # Checkpoint references
        orphaned_checkpoints = ExceptionCheckpoint.objects.filter(
            exception_request__isnull=True
        ).count()
        if orphaned_checkpoints > 0:
            self.log_error(f"{orphaned_checkpoints} checkpoints without exception")
        else:
            self.log_pass("All checkpoints have valid exception")
    
    def run_all(self):
        """Run full validation suite."""
        print("\n" + "="*60)
        print("SCHEMA FREEZE VALIDATION")
        print("="*60)
        
        self.validate_data_constraints()
        self.validate_foreign_keys()
        self.validate_indexes()
        self.validate_constraints()
        self.validate_workflow_logic()
        self.validate_referential_integrity()
        
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"✓ Passed:   {len(self.passed)}")
        print(f"⚠ Warnings: {len(self.warnings)}")
        print(f"✗ Errors:   {len(self.errors)}")
        
        if self.errors:
            print("\n⚠️  ERRORS FOUND - Address before migration:")
            for err in self.errors:
                print(f"  {err}")
            return False
        
        if self.warnings:
            print("\n⚠️  WARNINGS - Review before freeze:")
            for warn in self.warnings:
                print(f"  {warn}")
        
        if not self.errors:
            print("\n✅ SCHEMA FREEZE READY")
            return True


if __name__ == '__main__':
    validator = SchemaValidator()
    ready = validator.run_all()
    sys.exit(0 if ready else 1)
