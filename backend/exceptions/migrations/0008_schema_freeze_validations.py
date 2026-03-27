# Generated migration for schema freeze validations
# Adds missing constraints and indexes for production readiness

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exceptions', '0007_rename_riskissue_table_and_constraints'),
    ]

    operations = [
        # ============================================
        # 1. ADD RISK RATING CONSTRAINT (not null, choices)
        # ============================================
        migrations.AlterField(
            model_name='exceptionrequest',
            name='risk_rating',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Low', 'Low Risk'),
                    ('Medium', 'Medium Risk'),
                    ('High', 'High Risk'),
                    ('Critical', 'Critical Risk'),
                ],
                max_length=20,
                help_text='Risk rating category derived from risk score',
            ),
        ),
        
        # ============================================
        # 2. ADD NUMBER_OF_ASSETS CONSTRAINT (>= 1)
        # ============================================
        migrations.AlterField(
            model_name='exceptionrequest',
            name='number_of_assets',
            field=models.IntegerField(
                help_text='Number of assets affected by this exception (minimum 1)',
            ),
        ),
        migrations.AddConstraint(
            model_name='exceptionrequest',
            constraint=models.CheckConstraint(
                check=models.Q(number_of_assets__gte=1),
                name='exception_number_of_assets_gte_1',
            ),
        ),
        
        # ============================================
        # 3. ADD RISK_SCORE >= 0 CONSTRAINT
        # ============================================
        migrations.AddConstraint(
            model_name='exceptionrequest',
            constraint=models.CheckConstraint(
                check=models.Q(risk_score__gte=0) | models.Q(risk_score__isnull=True),
                name='exception_risk_score_gte_0_or_null',
            ),
        ),
        
        # ============================================
        # 4. SCHEDULER QUERY INDEXES (Critical)
        # ============================================
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(
                fields=['status', 'approval_deadline'],
                name='exception_status_deadline_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(
                fields=['status', 'exception_end_date'],
                name='exception_status_enddate_idx',
            ),
        ),
        # Index for reminder stage filtering (ReminderEngine)
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(
                fields=['reminder_stage', 'approval_deadline'],
                name='exception_reminder_deadline_idx',
            ),
        ),
        
        # ============================================
        # 5. BUSINESS UNIT QUERY INDEX
        # ============================================
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(
                fields=['business_unit', 'status'],
                name='exception_bu_status_idx',
            ),
        ),
        
        # ============================================
        # 6. AUDIT LOG OPTIMIZATION (already had this, ensure it exists)
        # ============================================
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(
                fields=['exception_request', '-timestamp'],
                name='auditlog_exception_timestamp_idx',
            ),
        ),
    ]
