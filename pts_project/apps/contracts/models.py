"""
Contract Management models for PTS.

Contracts are created by the Procurement Team after a tender is awarded.
Each contract type has its own milestone workflow:

  Lumpsum         → delivery_date countdown → Good Completion Certificate
  Framework       → 1-year period (renewable) → Purchase Orders (each like Lumpsum)
  Consultancy     → Inception → Payment → Completed
  Works           → Kickoff Meeting → Study Review → Start → Technical Handover
                    → Provisional Handover → Final Handover
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Contract(models.Model):
    CONTRACT_TYPE_CHOICES = [
        ('Goods', 'Goods'),
        ('Non-consultancy services', 'Non-consultancy services'),
        ('Consultancy Service', 'Consultancy Service'),
        ('Works', 'Works'),
    ]

    CONTRACT_STRUCTURE_CHOICES = [
        ('Lumpsum', 'Lumpsum'),
        ('Framework', 'Framework'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Renewed', 'Renewed'),       # Framework only
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    # ── Core fields ──────────────────────────────────────────────
    contract_number    = models.CharField(max_length=200, unique=True)
    contract_name      = models.CharField(max_length=500)
    contract_type      = models.CharField(max_length=50, choices=CONTRACT_TYPE_CHOICES)
    contract_structure = models.CharField(
        max_length=30, choices=CONTRACT_STRUCTURE_CHOICES,
        blank=True, default='',
        help_text='Lumpsum or Framework — the payment structure for Consultancy/Works contracts.'
    )
    status             = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Active')
    notes              = models.TextField(blank=True)

    # ── Budget & supplier ─────────────────────────────────────────
    contract_budget = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        help_text='Contract amount in RWF.',
    )
    supplier_name = models.CharField(
        max_length=500, blank=True,
        help_text='Supplier / contractor name (or Consultant name for Consultancy types).',
    )

    division = models.ForeignKey(
        'divisions.Division', on_delete=models.PROTECT,
        related_name='contracts', null=True, blank=True,
    )
    project_managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True, related_name='managed_contracts',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_contracts',
    )
    tender = models.ForeignKey(
        'procurement.Tender', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contracts',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Lumpsum fields ───────────────────────────────────────────
    delivery_date              = models.DateField(null=True, blank=True)
    lumpsum_start_date         = models.DateField(null=True, blank=True)   # countdown start
    original_delivery_date     = models.DateField(null=True, blank=True)   # before any extension
    extension_count            = models.PositiveIntegerField(default=0)
    extension_notes            = models.TextField(blank=True)
    milestone_extension_counts = models.JSONField(default=dict, blank=True,
        help_text='Per-milestone extension counts, e.g. {"study_review": 2}.')
    # ── Delivery receipt & evaluation ────────────────────────────
    received_date    = models.DateField(null=True, blank=True, help_text='Date goods/services were confirmed received.')
    received_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='received_contracts',
    )
    received_notes   = models.TextField(blank=True)
    evaluation_date  = models.DateField(null=True, blank=True)
    evaluation_notes = models.TextField(blank=True)
    completion_certificate_date = models.DateField(null=True, blank=True)
    completion_comment         = models.TextField(blank=True)
    performance_guarantee      = models.FileField(
        upload_to='performance_guarantees/contracts/',
        null=True, blank=True,
        help_text='Legacy single PG field — use PerformanceGuarantee model for multiple.',
    )
    document = models.FileField(
        upload_to='contracts/documents/',
        null=True, blank=True,
        help_text='Signed contract document uploaded at contract creation.',
    )

    # ── Framework fields ─────────────────────────────────────────
    framework_start_date  = models.DateField(null=True, blank=True)
    framework_end_date    = models.DateField(null=True, blank=True)   # start + 1 year
    is_renewed            = models.BooleanField(default=False)
    renewal_start_date    = models.DateField(null=True, blank=True)
    renewal_end_date      = models.DateField(null=True, blank=True)   # start + 1 more year

    # ── Consultancy Service fields ────────────────────────────────
    # Flow: Inception → Draft Report → Final Report → Payment
    # Each step: set target date → countdown → approve → advance
    inception_date          = models.DateField(null=True, blank=True)
    inception_approved      = models.BooleanField(default=False)
    draft_report_date       = models.DateField(null=True, blank=True)
    draft_report_approved   = models.BooleanField(default=False)
    final_report_date       = models.DateField(null=True, blank=True)
    final_report_approved   = models.BooleanField(default=False)
    payment_date            = models.DateField(null=True, blank=True)

    # ── Works fields (all dates set by Procurement Team) ─────────────────
    # Flow: Kickoff → Study Review → Approval → Work Start → Technical → Provisional → Final
    kickoff_meeting_date      = models.DateField(null=True, blank=True)
    kickoff_meeting_approved  = models.BooleanField(default=False)
    study_review_date         = models.DateField(null=True, blank=True)
    study_review_approved     = models.BooleanField(default=False)
    works_approval_date       = models.DateField(null=True, blank=True)
    works_approval_approved   = models.BooleanField(default=False)
    works_start_date          = models.DateField(null=True, blank=True)
    works_start_approved      = models.BooleanField(default=False)
    technical_handover_date   = models.DateField(null=True, blank=True)
    technical_handover_approved = models.BooleanField(default=False)
    provisional_handover_date = models.DateField(null=True, blank=True)
    provisional_handover_approved = models.BooleanField(default=False)
    final_handover_date       = models.DateField(null=True, blank=True)
    final_handover_approved   = models.BooleanField(default=False)

    class Meta:
        db_table = 'contracts'
        ordering = ['-created_at']
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'

    def __str__(self):
        return f'{self.contract_number} — {self.contract_name}'

    # ── Computed helpers ─────────────────────────────────────────

    @property
    def days_until_delivery(self):
        """For Lumpsum: days remaining until delivery_date (negative = overdue)."""
        if self.delivery_date:
            return (self.delivery_date - timezone.now().date()).days
        return None

    @property
    def lumpsum_progress_data(self):
        """Returns dict with progress info for the Lumpsum deadline progress bar."""
        if not self.delivery_date:
            return None
        start = self.lumpsum_start_date or self.created_at.date()
        today = timezone.now().date()
        total_days = (self.delivery_date - start).days
        elapsed = (today - start).days
        remaining = (self.delivery_date - today).days
        if total_days <= 0:
            pct = 100
        else:
            pct = min(100, max(0, round(elapsed / total_days * 100)))
        quarter_threshold = max(1, total_days // 4)
        return {
            'start_date':       start,
            'delivery_date':    self.delivery_date,
            'total_days':       total_days,
            'elapsed':          elapsed,
            'remaining':        remaining,
            'pct':              pct,
            'is_overdue':       remaining < 0,
            'overdue_days':     abs(remaining) if remaining < 0 else 0,
            'is_quarter_alert': 0 <= remaining <= quarter_threshold,
            'is_warning':       0 <= remaining <= 7,
            'quarter_threshold': quarter_threshold,
        }

    @property
    def framework_active_end(self):
        """The currently-active end date (renewal_end_date if renewed, else framework_end_date)."""
        if self.is_renewed and self.renewal_end_date:
            return self.renewal_end_date
        return self.framework_end_date

    @property
    def framework_days_remaining(self):
        end = self.framework_active_end
        if end:
            return (end - timezone.now().date()).days
        return None

    @property
    def current_works_step(self):
        """Return the label of the latest completed Works milestone."""
        if self.final_handover_date:
            return 'Final Handover'
        if self.provisional_handover_date:
            return 'Provisional Handover'
        if self.technical_handover_date:
            return 'Technical Handover'
        if self.works_start_date:
            return 'Work Start'
        if self.works_approval_date:
            return 'Approval'
        if self.study_review_date:
            return 'Study Review'
        if self.kickoff_meeting_date:
            return 'Kickoff Meeting'
        return 'Pending'

    @property
    def current_consultancy_step(self):
        if self.payment_date:
            return 'Payment'
        if self.final_report_approved:
            return 'Final Report Approved'
        if self.final_report_date:
            return 'Final Report'
        if self.draft_report_approved:
            return 'Draft Report Approved'
        if self.draft_report_date:
            return 'Draft Report'
        if self.inception_approved:
            return 'Inception Approved'
        if self.inception_date:
            return 'Inception'
        return 'Pending'

    def consultancy_step_countdown(self, step_date, prev_date_or_created):
        """Like lumpsum_progress_data but for a consultancy step countdown."""
        if not step_date:
            return None
        start = prev_date_or_created
        today = timezone.now().date()
        total_days = max(1, (step_date - start).days)
        elapsed    = (today - start).days
        remaining  = (step_date - today).days
        pct = min(100, max(0, round(elapsed / total_days * 100)))
        quarter_threshold = max(1, total_days // 4)
        return {
            'start_date':       start,
            'target_date':      step_date,
            'total_days':       total_days,
            'elapsed':          elapsed,
            'remaining':        remaining,
            'pct':              pct,
            'is_overdue':       remaining < 0,
            'overdue_days':     abs(remaining) if remaining < 0 else 0,
            'is_quarter_alert': 0 <= remaining <= quarter_threshold,
            'is_warning':       0 <= remaining <= 7,
        }


class PurchaseOrder(models.Model):
    """
    Used for Framework contracts — one or many POs during the contract period.
    Each PO behaves like a mini-lumpsum: delivery_date → completion certificate.
    """
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Delivered', 'Delivered'),
        ('Completed', 'Completed'),
    ]

    contract    = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='purchase_orders')
    po_number   = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    issued_date = models.DateField()
    delivery_date = models.DateField()
    original_delivery_date = models.DateField(null=True, blank=True)
    extension_count = models.PositiveIntegerField(default=0)
    extension_notes = models.TextField(blank=True)
    completion_certificate_date = models.DateField(null=True, blank=True)
    completion_comment  = models.TextField(blank=True)
    performance_guarantee = models.FileField(
        upload_to='performance_guarantees/pos/',
        null=True, blank=True,
        help_text='Legacy single PG field — use POPerformanceGuarantee model for multiple.',
    )
    document = models.FileField(
        upload_to='purchase_orders/documents/',
        null=True, blank=True,
        help_text='PO document uploaded when the purchase order is issued.',
    )
    # ── Delivery receipt & evaluation ────────────────────────────
    received_date    = models.DateField(null=True, blank=True)
    received_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='received_purchase_orders',
    )
    received_notes   = models.TextField(blank=True)
    evaluation_date  = models.DateField(null=True, blank=True)
    evaluation_notes = models.TextField(blank=True)
    status      = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Active')
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_purchase_orders',
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_purchase_orders'
        ordering = ['-issued_date']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        return self.po_number

    @property
    def days_until_delivery(self):
        return (self.delivery_date - timezone.now().date()).days

    @property
    def progress_data(self):
        """Returns dict with progress info for the PO delivery progress bar."""
        today = timezone.now().date()
        total_days = (self.delivery_date - self.issued_date).days
        elapsed = (today - self.issued_date).days
        remaining = (self.delivery_date - today).days
        if total_days <= 0:
            pct = 100
        else:
            pct = min(100, max(0, round(elapsed / total_days * 100)))
        quarter_threshold = max(1, total_days // 4)
        return {
            'total_days':       total_days,
            'elapsed':          elapsed,
            'remaining':        remaining,
            'pct':              pct,
            'is_overdue':       remaining < 0,
            'overdue_days':     abs(remaining) if remaining < 0 else 0,
            'is_quarter_alert': 0 <= remaining <= quarter_threshold,
            'is_warning':       0 <= remaining <= 7,
            'quarter_threshold': quarter_threshold,
        }


class ContractComment(models.Model):
    """Progress notes / comments on a contract or a specific PO."""
    contract       = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='comments')
    purchase_order = models.ForeignKey(
        'PurchaseOrder', on_delete=models.CASCADE,
        null=True, blank=True, related_name='comments',
    )
    text       = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='contract_comments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_comments'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contract.contract_number} comment by {getattr(self.created_by, "full_name", "—")}'


class ContractMilestoneAlert(models.Model):
    """User-configured alert: notify X days before a milestone target date."""
    MILESTONE_CHOICES = [
        # Lumpsum
        ('delivery',            'Delivery Date'),
        # Framework
        ('framework_expiry',    'Framework Expiry'),
        # Consultancy
        ('inception',           'Inception'),
        ('draft_report',        'Draft Report'),
        ('final_report',        'Final Report'),
        ('payment',             'Payment'),
        # Works
        ('kickoff_meeting',     'Kickoff Meeting'),
        ('study_review',        'Study Review'),
        ('works_approval',      'Works Approval'),
        ('works_start',         'Work Start'),
        ('technical_handover',  'Technical Handover'),
        ('provisional_handover','Provisional Handover'),
        ('final_handover',      'Final Handover'),
    ]

    contract          = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='milestone_alerts')
    milestone_key     = models.CharField(max_length=50, choices=MILESTONE_CHOICES)
    target_date       = models.DateField(help_text='Target/deadline date for this milestone.')
    alert_days_before = models.PositiveIntegerField(default=7, help_text='Send alert this many days before target_date.')
    created_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='milestone_alerts',
    )
    notified_at       = models.DateTimeField(null=True, blank=True)
    is_active         = models.BooleanField(default=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_milestone_alerts'
        unique_together = [('contract', 'milestone_key')]
        ordering = ['target_date']

    def __str__(self):
        return f'{self.contract.contract_number} — {self.milestone_key} alert ({self.alert_days_before}d before {self.target_date})'

    @property
    def should_fire_today(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.is_active and not self.notified_at and (self.target_date - today).days <= self.alert_days_before


class ContractHistory(models.Model):
    """Audit trail for all contract-level and PO-level actions."""
    contract   = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='history')
    action     = models.CharField(max_length=200)
    notes      = models.TextField(blank=True)
    action_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='contract_actions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_history'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contract.contract_number} — {self.action}'


class PerformanceGuarantee(models.Model):
    """Multiple performance guarantees attached to a Contract."""
    contract    = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='performance_guarantees')
    expiry_date = models.DateField(null=True, blank=True, help_text='Expiry date of this performance guarantee.')
    description = models.CharField(max_length=500, blank=True)
    file        = models.FileField(upload_to='performance_guarantees/contracts/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_contract_pgs',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_performance_guarantees'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'PG for {self.contract.contract_number} — {self.uploaded_at.date()}'

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None


class POPerformanceGuarantee(models.Model):
    """Multiple performance guarantees attached to a PurchaseOrder."""
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='performance_guarantees',
    )
    expiry_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    file        = models.FileField(upload_to='performance_guarantees/pos/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_po_pgs',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'po_performance_guarantees'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'PG for {self.purchase_order.po_number} — {self.uploaded_at.date()}'

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None


class ContractCommunication(models.Model):
    """
    Formal communication log on a contract.
    Distinct from ContractComment (quick progress notes).
    Accessible by Procurement Team, HOD/DM, and Project Managers.
    Supports optional file attachment.
    """
    contract    = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='communications')
    subject     = models.CharField(max_length=500, blank=True)
    message     = models.TextField()
    attachment  = models.FileField(
        upload_to='contract_communications/',
        null=True, blank=True,
    )
    sent_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='contract_communications',
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_communications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contract.contract_number} — {self.subject or "Communication"} ({self.created_at.date()})'

    @property
    def attachment_filename(self):
        import os
        return os.path.basename(self.attachment.name) if self.attachment else ''
