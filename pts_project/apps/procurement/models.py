"""
Procurement models for PTS.
Includes Procurement Calls, Submissions, Bids, and Comments.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import BaseModel, AuditableModel, TimestampMixin


class ProcurementCall(BaseModel):
    """
    Procurement Call model.
    CBM initiates procurement calls requesting divisions to submit their needs.
    """
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Active', 'Active'),
        ('Extended', 'Extended'),
        ('Closed', 'Closed'),
        ('Cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='call_id'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    reference_number = models.CharField(max_length=50, unique=True)
    
    # Dates
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    extended_date = models.DateTimeField(null=True, blank=True)
    
    # Instructions and scope
    instructions = models.TextField(blank=True, null=True)
    scope = models.TextField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    
    # Creator
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_calls',
        db_column='created_by'
    )
    
    # Budget ceiling (optional)
    budget_ceiling = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Allow late submissions
    allow_late_submissions = models.BooleanField(default=False)
    
    # Call document
    call_document = models.FileField(
        upload_to='procurement_calls/%Y/%m/',
        null=True,
        blank=True,
        help_text='Supporting document for the procurement call'
    )
    
    class Meta:
        db_table = 'procurement_calls'
        verbose_name = 'Procurement Call'
        verbose_name_plural = 'Procurement Calls'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reference_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Auto-generate reference number if not provided
        if not self.reference_number:
            year = timezone.now().year
            count = ProcurementCall.objects.filter(
                created_at__year=year
            ).count() + 1
            self.reference_number = f"PTS-{year}-{count:04d}"
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if the call is currently active."""
        now = timezone.now()
        effective_end = self.extended_date or self.end_date
        return self.status == 'Active' and self.start_date <= now <= effective_end
    
    @property
    def is_overdue(self):
        """Check if the call deadline has passed."""
        effective_end = self.extended_date or self.end_date
        return timezone.now() > effective_end
    
    @property
    def days_remaining(self):
        """Calculate days remaining until deadline."""
        effective_end = self.extended_date or self.end_date
        delta = effective_end - timezone.now()
        return max(0, delta.days)
    
    @property
    def submission_count(self):
        """Get number of submissions for this call."""
        return self.submissions.count()


class Submission(AuditableModel):
    """
    Submission model.
    Represents a division's procurement request in response to a call.
    """
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Call Issued', 'Call Issued'),
        ('HOD/DM Submit', 'HOD/DM Submit'),
        ('Review of Procurement Draft', 'Review of Procurement Draft'),
        ('Returned', 'Returned for Clarification'),
        ('Submit Compiled Document', 'Submit Compiled Document'),
        ('CBM Review', 'CBM Review'),
        ('Publish Plan', 'Publish Plan'),
        ('Plan Published', 'Plan Published'),
        ('Prepare Tender Document', 'Prepare Tender Document'),
        ('CBM Review TD', 'CBM Review Tender Document'),
        ('Publication of TD', 'Publication of TD'),
        ('Opening', 'Opening'),
        ('Evaluation', 'Evaluation'),
        ('CBM Approval', 'CBM Approval'),
        ('Notify Bidders', 'Notify Bidders'),
        ('Contract Negotiation', 'Contract Negotiation'),
        ('Contract Drafting', 'Contract Drafting'),
        ('Legal Review', 'Legal Review'),
        ('Supplier Approval', 'Supplier Approval'),
        ('MINIJUST Legal Review', 'MINIJUST Legal Review'),
        ('Awarded', 'Awarded'),
        ('Completed', 'Completed'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='submission_id'
    )
    
    # Reference
    tracking_reference = models.CharField(max_length=50, unique=True, editable=False)
    
    # Links
    call = models.ForeignKey(
        ProcurementCall,
        on_delete=models.CASCADE,
        related_name='submissions',
        db_column='call_id'
    )
    division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.CASCADE,
        related_name='submissions',
        db_column='division_id'
    )
    
    # Item details
    item_name = models.CharField(max_length=255)
    item_description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    number_of_procurement_items = models.PositiveIntegerField(default=1, help_text="Number of procurement items/requests in this submission")
    
    # Quantity and pricing
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_of_measure = models.CharField(max_length=50, default='Units')
    estimated_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    total_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        editable=False,
        default=Decimal('0.00')
    )
    
    # Justification
    justification = models.TextField(blank=True, null=True)
    priority = models.CharField(
        max_length=20,
        choices=[
            ('Low', 'Low'),
            ('Medium', 'Medium'),
            ('High', 'High'),
            ('Critical', 'Critical'),
        ],
        default='Medium'
    )
    
    # Expected timeline
    expected_delivery_date = models.DateField(null=True, blank=True)
    
    # Deadline and completion tracking
    cbm_review_deadline = models.DateField(null=True, blank=True, help_text="Deadline for CBM review")
    procurement_deadline = models.DateField(null=True, blank=True, help_text="Expected completion deadline for procurement process")
    expected_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    
    # Workflow
    current_stage = models.ForeignKey(
        'workflows.WorkflowStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_submissions',
        db_column='current_stage_id'
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Draft')
    
    # Submitted by
    submitted_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_submissions'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Umucyo integration
    umucyo_reference = models.CharField(max_length=100, blank=True, null=True)
    umucyo_link = models.URLField(blank=True, null=True)
    
    # Award details (JSON: supplier_name, award_amount, award_date)
    award_details = models.JSONField(null=True, blank=True)
    
    # Attachments (store file paths)
    attachments = models.JSONField(default=list, blank=True)
    
    # TIMELINE AUTOMATION FIELDS
    # Procurement method selection (chosen when entering specific steps)
    procurement_method = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Selected procurement method (e.g., 'International Competitive', 'National Restricted')"
    )
    
    # Timeline tracking
    current_stage_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Deadline for current workflow stage"
    )
    timeline_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approaching', 'Approaching Deadline'),
            ('expired', 'Deadline Expired'),
            ('none', 'No Timeline'),
        ],
        default='none',
        help_text="Current timeline status"
    )
    bid_validity_extension_used = models.BooleanField(
        default=False,
        help_text="Track if 60-day extension was already used for bid validity period"
    )
    timeline_last_checked = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last timeline status update"
    )
    
    class Meta:
        db_table = 'submissions'
        verbose_name = 'Submission'
        verbose_name_plural = 'Submissions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['division', 'status']),
            models.Index(fields=['call', 'status']),
        ]
    
    def __str__(self):
        return f"{self.tracking_reference} - {self.item_name}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate total budget
        self.total_budget = self.quantity * self.estimated_unit_price
        
        # Auto-generate tracking reference
        if not self.tracking_reference:
            year = timezone.now().year
            count = Submission.objects.filter(
                created_at__year=year
            ).count() + 1
            div_code = self.division.code if self.division else 'GEN'
            self.tracking_reference = f"SUB-{year}-{div_code}-{count:05d}"
        
        super().save(*args, **kwargs)
    
    @property
    def is_editable(self):
        """Check if the submission can still be edited."""
        return self.status in ['Draft', 'Returned']
    
    @property
    def is_late(self):
        """Check if submission was made after the deadline."""
        if not self.submitted_at or not self.call:
            return False
        effective_end = self.call.extended_date or self.call.end_date
        return self.submitted_at > effective_end
    
    @property
    def days_at_current_stage(self):
        """Calculate days at current stage."""
        last_history = self.workflow_history.order_by('-created_at').first()
        if last_history:
            delta = timezone.now() - last_history.created_at
            return delta.days
        return (timezone.now() - self.created_at).days
    
    def submit(self, user):
        """Submit the procurement request."""
        from apps.workflows.models import WorkflowStage
        
        self.status = 'HOD/DM Submit'
        self.submitted_by = user
        self.submitted_at = timezone.now()
        
        # Set to stage 2 (HOD/DM Submit)
        stage = WorkflowStage.objects.filter(order=2).first()
        if stage:
            self.current_stage = stage
        
        self.save()
    
    def set_timeline_deadline(self, stage_name, procurement_method=None, tender_type=None):
        """
        Calculate and set the deadline for the current stage.
        
        Args:
            stage_name: Name of the workflow stage
            procurement_method: Selected procurement method (if applicable)
            tender_type: 'International' or 'National' (for contract stages)
        """
        from apps.procurement.timeline_utils import calculate_deadline, get_timeline_for_stage
        
        # Store the procurement method if provided
        if procurement_method:
            self.procurement_method = procurement_method
        
        # Calculate the deadline
        start_date = timezone.now()
        deadline = calculate_deadline(start_date, stage_name, procurement_method, tender_type)
        
        if deadline:
            self.current_stage_deadline = deadline
            self.timeline_status = 'pending'
        else:
            self.current_stage_deadline = None
            self.timeline_status = 'none'
        
        self.timeline_last_checked = timezone.now()
        self.save()
    
    def update_timeline_status(self):
        """
        Update the timeline status based on current date and deadline.
        Called by periodic task to check which submissions are approaching/overdue.
        """
        from datetime import timedelta
        
        if not self.current_stage_deadline or self.timeline_status == 'none':
            return
        
        now = timezone.now()
        days_until_deadline = (self.current_stage_deadline - now).days
        
        if days_until_deadline < 0:
            # Deadline has passed
            self.timeline_status = 'expired'
        elif days_until_deadline <= 7:
            # Within 7 days of deadline
            self.timeline_status = 'approaching'
        else:
            # Still pending
            self.timeline_status = 'pending'
        
        self.timeline_last_checked = timezone.now()
        self.save()
    
    @property
    def timeline_days_remaining(self):
        """Get number of calendar days remaining until deadline."""
        if not self.current_stage_deadline:
            return None
        
        from apps.procurement.timeline_utils import get_calendar_days_until
        return get_calendar_days_until(timezone.now(), self.current_stage_deadline)
    
    @property
    def is_timeline_expired(self):
        """Check if current stage deadline has passed."""
        if not self.current_stage_deadline:
            return False
        return timezone.now() > self.current_stage_deadline
    
    @property
    def timeline_progress_percentage(self):
        """
        Calculate the percentage of timeline used (0-100).
        Returns the progress as a percentage for the progress bar.
        """
        if not self.current_stage_deadline or not self.timeline_last_checked:
            return 0
        
        from apps.procurement.timeline_utils import get_calendar_days_until
        
        # Calculate days elapsed since timeline was set
        days_elapsed = get_calendar_days_until(self.timeline_last_checked, timezone.now())
        
        # Calculate total days from last checked to deadline
        total_days = get_calendar_days_until(self.timeline_last_checked, self.current_stage_deadline)
        
        if total_days <= 0:
            return 100  # If already past deadline
        
        # Calculate percentage
        progress = (days_elapsed / total_days) * 100
        return min(100, max(0, int(progress)))  # Clamp between 0-100
    
    def extend_bid_validity(self):
        """
        Extend bid validity period by 60 days (can only be used once).
        
        Returns:
            True if extension was applied, False if already extended or not in bid validity stage
        """
        if self.bid_validity_extension_used:
            return False
        
        if not self.current_stage_deadline:
            return False
        
        from apps.procurement.timeline_utils import add_calendar_days
        from datetime import timedelta
        
        # Add 60 calendar days to current deadline
        self.current_stage_deadline = add_calendar_days(self.current_stage_deadline, 60)
        self.bid_validity_extension_used = True
        self.timeline_last_checked = timezone.now()
        self.save()
        
        return True


class Tender(models.Model):
    """
    Individual tender tracked on Umucyo e-procurement. Created from a Published Plan submission.
    Multiple tenders can belong to the same submission.
    The tender_number from Umucyo is the primary key.
    """
    PROCUREMENT_METHOD_CHOICES = [
        ('International Competitive', 'International Competitive'),
        ('International Restricted', 'International Restricted'),
        ('National Competitive', 'National Competitive'),
        ('National Restricted', 'National Restricted'),
        ('Request for Quotations', 'Request for Quotations'),
        ('National Open Simplified', 'National Open Simplified'),
        ('National Restricted Simplified', 'National Restricted Simplified'),
        ('Prequalification', 'Prequalification'),
        ('Single Source', 'Single Source'),
        ('Force Account', 'Force Account'),
        ('Two Stage Tendering', 'Two Stage Tendering'),
        ('Turnkey', 'Turnkey'),
        ('Community Participation', 'Community Participation'),
        ('Competitive Dialogue', 'Competitive Dialogue'),
        ('Design and Build', 'Design and Build'),
        ('Pre-financing', 'Pre-financing'),
        ('Reverse Auctioning', 'Reverse Auctioning'),
    ]

    TENDER_STATUS_CHOICES = [
        ('Prepare Tender Document', 'Prepare Tender Document'),
        ('CBM Review TD', 'CBM Review Tender Document'),
        ('Publication of TD', 'Publication of Tender Document'),
        ('Opening', 'Opening'),
        ('Evaluation', 'Evaluation'),
        ('CBM Approval', 'CBM Approval'),
        ('Notify Bidders', 'Notify Bidders'),
        ('Contract Negotiation', 'Contract Negotiation'),
        ('Contract Drafting', 'Contract Drafting'),
        ('Legal Review', 'Legal Review'),
        ('Supplier Approval', 'Supplier Approval'),
        ('MINIJUST Legal Review', 'MINIJUST Legal Review'),
        ('Awarded', 'Awarded'),
        ('Completed', 'Completed'),
        ('Returned', 'Returned for Revision'),
        ('Cancelled', 'Cancelled'),
    ]

    # Stage order map — maps status to WorkflowStage order
    STAGE_ORDER_MAP = {
        'Prepare Tender Document': 7,
        'CBM Review TD': 8,
        'Publication of TD': 9,
        'Opening': 10,
        'Evaluation': 11,
        'CBM Approval': 12,
        'Notify Bidders': 13,
        'Contract Negotiation': 14,
        'Contract Drafting': 15,
        'Legal Review': 16,
        'Supplier Approval': 17,
        'MINIJUST Legal Review': 18,
        'Awarded': 19,
        'Completed': 20,
    }

    # Tender number from Umucyo e-procurement — the primary key
    tender_number = models.CharField(
        max_length=100,
        primary_key=True,
        help_text='Tender reference number from Umucyo e-procurement platform'
    )
    tender_title = models.CharField(
        max_length=255,
        help_text='Official title of the tender as registered on Umucyo'
    )

    # A submission can have multiple tenders (e.g. split procurements)
    submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenders',
        help_text='The published plan submission this tender was created from (optional)'
    )

    # Current stage in the tender workflow
    status = models.CharField(
        max_length=50,
        choices=TENDER_STATUS_CHOICES,
        default='Prepare Tender Document',
        help_text='Current stage of this individual tender'
    )
    current_stage = models.ForeignKey(
        'workflows.WorkflowStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_tenders',
        help_text='WorkflowStage entry matching the current tender status'
    )

    # Procurement method (selected when creating the tender)
    procurement_method = models.CharField(
        max_length=100,
        choices=PROCUREMENT_METHOD_CHOICES,
        help_text='Procurement method as defined by RPPA guidelines'
    )

    # Umucyo link and date
    umucyo_link = models.URLField(
        blank=True,
        null=True,
        help_text='Direct link to the tender on Umucyo platform'
    )
    approval_date = models.DateField(
        null=True,
        blank=True,
        help_text='Latest approval/action date recorded in Umucyo'
    )

    # Tender dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Who created it
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tenders'
    )

    class Meta:
        db_table = 'tenders'
        verbose_name = 'Tender'
        verbose_name_plural = 'Tenders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tender_number} — {self.tender_title}"

    @property
    def stage_number(self):
        """Returns the tender-local stage position (1-14)."""
        keys = list(self.STAGE_ORDER_MAP.keys())
        try:
            return keys.index(self.status) + 1
        except ValueError:
            return 1

    @property
    def progress_percentage(self):
        """0-100 progress through the 14 tender stages."""
        idx = list(self.STAGE_ORDER_MAP.keys()).index(self.status) if self.status in self.STAGE_ORDER_MAP else 0
        return int((idx / (len(self.STAGE_ORDER_MAP) - 1)) * 100)

    @property
    def is_completed(self):
        return self.status == 'Completed'

    @property
    def is_with_cbm(self):
        return self.status in ('CBM Review TD', 'CBM Approval')


class TenderHistory(models.Model):
    """
    Audit trail for individual tender stage transitions.
    """
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name='history'
    )
    from_status = models.CharField(max_length=50, blank=True, help_text='Status before the action')
    to_status = models.CharField(max_length=50, help_text='Status after the action')
    action = models.CharField(
        max_length=20,
        default='advance',
        choices=[('create', 'Created'), ('advance', 'Advanced'), ('return', 'Returned'), ('cancel', 'Cancelled'), ('note', 'Note Added')]
    )
    comments = models.TextField(blank=True)
    action_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='tender_actions'
    )
    approval_date = models.DateField(null=True, blank=True, help_text='Umucyo approval date for this action')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tender_history'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.tender_id}: {self.from_status} → {self.to_status}'


class Bid(BaseModel):
    """
    Bid model.
    Represents a supplier's bid for a submission/tender.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='bid_id'
    )
    
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='bids',
        db_column='submission_id'
    )
    
    # Supplier information
    supplier_name = models.CharField(max_length=255)
    supplier_tin = models.CharField(max_length=50, blank=True, null=True)
    supplier_contact = models.CharField(max_length=255, blank=True, null=True)
    supplier_email = models.EmailField(blank=True, null=True)
    
    # Bid details
    bid_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='RWF')
    
    # Scoring
    technical_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    financial_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Status
    is_winner = models.BooleanField(default=False)
    is_disqualified = models.BooleanField(default=False)
    disqualification_reason = models.TextField(blank=True, null=True)
    
    # Submission date
    submission_date = models.DateTimeField(auto_now_add=True)
    
    # Documents (store file paths)
    documents = models.JSONField(default=list, blank=True)
    
    # Evaluation notes
    evaluation_notes = models.TextField(blank=True, null=True)
    evaluated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluated_bids'
    )
    evaluated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bids'
        verbose_name = 'Bid'
        verbose_name_plural = 'Bids'
        ordering = ['-submission_date']
    
    def __str__(self):
        return f"{self.supplier_name} - {self.bid_amount} {self.currency}"
    
    def calculate_total_score(self):
        """Calculate total score from technical and financial scores."""
        if self.technical_score is not None and self.financial_score is not None:
            # Typical weighting: 70% technical, 30% financial
            self.total_score = (self.technical_score * Decimal('0.7')) + (self.financial_score * Decimal('0.3'))
            self.save(update_fields=['total_score'])


class Comment(BaseModel):
    """
    Comment model for threaded discussions on submissions.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    # Comment author
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='comments'
    )
    
    # Content
    content = models.TextField()
    
    # Threading (for replies)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Comment type
    comment_type = models.CharField(
        max_length=20,
        choices=[
            ('comment', 'General Comment'),
            ('clarification', 'Request for Clarification'),
            ('response', 'Response to Clarification'),
            ('approval', 'Approval Note'),
            ('rejection', 'Rejection Reason'),
        ],
        default='comment'
    )
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_comments'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'submission_comments'
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author} on {self.submission.tracking_reference}"
    
    def resolve(self, user):
        """Mark comment as resolved."""
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save()


class Attachment(BaseModel):
    """
    Attachment model for storing files related to submissions.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='submission_attachments'
    )
    
    # File information
    file = models.FileField(upload_to='submissions/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    file_size = models.PositiveIntegerField()  # in bytes
    
    # Metadata
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_attachments'
    )
    
    class Meta:
        db_table = 'submission_attachments'
        verbose_name = 'Attachment'
        verbose_name_plural = 'Attachments'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.original_filename


class SubmissionDocument(models.Model):
    """
    Supporting documents for a submission.
    Stores procurement plan, technical specifications, market survey, etc.
    """
    DOCUMENT_TYPE_CHOICES = [
        ('procurement_plan', 'Procurement Plan'),
        ('technical_specification', 'Technical Specification'),
        ('market_survey', 'Market Survey'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='submission_document_id'
    )
    
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='supporting_documents',
        db_column='submission_id'
    )
    
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
        db_column='document_type'
    )
    
    file = models.FileField(
        upload_to='submission_documents/%Y/%m/',
        help_text='Maximum file size: 10MB'
    )
    
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # in bytes
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_submission_documents'
    )
    
    class Meta:
        db_table = 'submission_documents'
        verbose_name = 'Submission Document'
        verbose_name_plural = 'Submission Documents'
        ordering = ['document_type', '-uploaded_at']
        indexes = [
            models.Index(fields=['submission', 'document_type']),
        ]
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.original_filename}"


class TimelineConfiguration(models.Model):
    """
    Configuration for procurement timeline requirements.
    Defines how many business days each workflow stage should take.
    """
    STAGE_CHOICES = [
        ('Publication of TD', 'Publication of Tender Documents'),
        ('Evaluation', 'Evaluation of Bids/Proposals'),
        ('Notification', 'Notification to Bidders'),
        ('Bid Validity Period', 'Bid Validity Period'),
        ('Contract Signature', 'Contract Signature'),
    ]
    
    stage_name = models.CharField(max_length=100, choices=STAGE_CHOICES)
    
    # For stages that depend on procurement method
    procurement_method = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Leave blank if timeline applies to all methods"
    )
    
    # Timeline in business days
    min_days = models.PositiveIntegerField(
        default=0,
        help_text="Minimum business days required for this stage"
    )
    max_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Maximum business days allowed for this stage (if applicable)"
    )
    
    # Whether this timeline can be extended
    is_extendable = models.BooleanField(
        default=False,
        help_text="Can this timeline be extended beyond max_days?"
    )
    extension_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Number of days for single extension"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timeline_configuration'
        verbose_name = 'Timeline Configuration'
        verbose_name_plural = 'Timeline Configurations'
        unique_together = ('stage_name', 'procurement_method')
        ordering = ['stage_name', 'procurement_method']
    
    def __str__(self):
        if self.procurement_method:
            return f"{self.stage_name} - {self.procurement_method} ({self.min_days}-{self.max_days} days)"
        return f"{self.stage_name} ({self.min_days} days)"


class CompiledDocument(models.Model):
    """
    A compiled procurement document submitted by the Procurement Team.
    Covers all divisions. Procurement compiles, sends to CBM, then publishes.
    """
    STATUS_CHOICES = [
        ('Sent to CBM', 'Sent to CBM'),
        ('Published', 'Published'),
    ]
    document_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='compiled_documents/')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Sent to CBM')
    submitted_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='compiled_documents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compiled_document'
        verbose_name = 'Compiled Document'
        verbose_name_plural = 'Compiled Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document_name} ({self.status})'

