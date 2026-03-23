"""
Workflow models for PTS.
Implements the 9-stage procurement lifecycle.
"""
import uuid
from django.db import models
from apps.core.models import TimestampMixin


class WorkflowStage(models.Model):
    """
    Workflow Stage model.
    Represents the detailed procurement lifecycle stages:
    1. Call Issued
    2. HOD/DM Submit
    3. Review of Procurement Draft
    4. CBM Review (Initial)
    5. Publish Plan
    6. Prepare Tender Document
    7. CBM Review (Tender)
    8. Publication of TD
    9. Bidding
    10. Evaluation
    11. CBM Approval
    12. Notify Bidders
    13. Contract Negotiation
    14. Contract Drafting
    15. Legal Review
    16. Supplier Approval (by Procurement Team)
    17. MINIJUST Legal Review (if > 500M RWF)
    18. Awarded
    19. Completed
    Plus: Returned for Clarification (can occur at any review stage)
    """
    STAGE_CHOICES = [
        ('Call Issued', 'Call Issued'),
        ('HOD/DM Submit', 'HOD/DM Submit'),
        ('Review of Procurement Draft', 'Review of Procurement Draft'),
        ('Submit Compiled Document', 'Submit Compiled Document'),
        ('CBM Review', 'CBM Review'),
        ('Publish Plan', 'Publish Plan'),
        ('Prepare Tender Document', 'Prepare Tender Document'),
        ('CBM Review TD', 'CBM Review Tender Document'),
        ('Publication of TD', 'Publication of TD'),
        ('Bidding', 'Bidding'),
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
    ]

    STAGE_TYPE_CHOICES = [
        ('internal', 'Internal'),
        ('transition', 'Transition'),
        ('external', 'External'),
    ]
    
    id = models.AutoField(primary_key=True, db_column='stage_id')
    name = models.CharField(
        max_length=50,
        choices=STAGE_CHOICES,
        unique=True,
        db_column='stage_name'
    )
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(unique=True)
    
    # Expected duration at this stage (in days)
    expected_duration_days = models.PositiveIntegerField(default=7)
    
    # Who can move submissions to this stage
    allowed_roles = models.JSONField(default=list, blank=True)
    
    # Visual representation
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    icon = models.CharField(max_length=50, default='circle')
    
    # Is this a terminal stage?
    is_terminal = models.BooleanField(default=False)

    # Stage classification
    stage_type = models.CharField(
        max_length=20,
        choices=STAGE_TYPE_CHOICES,
        default='external',
        help_text='internal: HOD/DM visible; transition: bridge steps; external: e-procurement tracking'
    )

    class Meta:
        db_table = 'workflow_stages'
        verbose_name = 'Workflow Stage'
        verbose_name_plural = 'Workflow Stages'
        ordering = ['order']
    
    def __str__(self):
        return f"{self.order}. {self.name}"
    
    @property
    def next_stage(self):
        """Get the next stage in the workflow."""
        return WorkflowStage.objects.filter(order=self.order + 1).first()
    
    @property
    def previous_stage(self):
        """Get the previous stage in the workflow."""
        return WorkflowStage.objects.filter(order=self.order - 1).first()


class WorkflowHistory(TimestampMixin):
    """
    Workflow History model.
    Tracks all transitions between stages for audit purposes.
    """
    ACTION_CHOICES = [
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('return', 'Returned'),
        ('publish', 'Published'),
        ('start_bidding', 'Bidding Started'),
        ('evaluate', 'Evaluation Started'),
        ('award', 'Awarded'),
        ('complete', 'Completed'),
        ('cancel', 'Cancelled'),
        ('status_update', 'Status Updated'),
        ('comment', 'Comment Added'),
        ('deadline_extended', 'Deadline Extended'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='history_id'
    )
    
    submission = models.ForeignKey(
        'procurement.Submission',
        on_delete=models.CASCADE,
        related_name='workflow_history',
        db_column='submission_id'
    )
    
    # Stage transition
    from_stage = models.ForeignKey(
        WorkflowStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transitions_from',
        db_column='from_stage_id'
    )
    to_stage = models.ForeignKey(
        WorkflowStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transitions_to',
        db_column='to_stage_id'
    )
    
    # Action details
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    action_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='workflow_actions',
        db_column='action_by'
    )
    comments = models.TextField(blank=True, null=True)
    
    # Umucyo approval date (for stages from Publish Plan onwards)
    approval_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when this approval occurred in Umucyo (from Publish Plan stage onwards)'
    )
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Time spent at previous stage (for analytics)
    time_at_previous_stage = models.DurationField(null=True, blank=True)
    
    class Meta:
        db_table = 'workflow_history'
        verbose_name = 'Workflow History'
        verbose_name_plural = 'Workflow Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.submission.tracking_reference}: {self.action} at {self.created_at}"
    
    def save(self, *args, **kwargs):
        # Calculate time at previous stage
        if self.from_stage:
            previous_history = WorkflowHistory.objects.filter(
                submission=self.submission,
                to_stage=self.from_stage
            ).order_by('-created_at').first()
            
            if previous_history:
                from django.utils import timezone
                self.time_at_previous_stage = timezone.now() - previous_history.created_at
        
        super().save(*args, **kwargs)


class WorkflowConfiguration(models.Model):
    """
    Configuration for workflow behavior.
    """
    stage = models.ForeignKey(
        WorkflowStage,
        on_delete=models.CASCADE,
        related_name='configurations'
    )
    
    # Allowed transitions from this stage
    allowed_next_stages = models.ManyToManyField(
        WorkflowStage,
        related_name='allowed_from_stages',
        blank=True
    )
    
    # Required approvals
    required_approval_roles = models.JSONField(default=list, blank=True)
    minimum_approvals = models.PositiveIntegerField(default=1)
    
    # Auto-transition rules
    auto_transition_after_days = models.PositiveIntegerField(null=True, blank=True)
    auto_transition_to = models.ForeignKey(
        WorkflowStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auto_transition_from'
    )
    
    # Escalation rules
    escalation_after_days = models.PositiveIntegerField(null=True, blank=True)
    escalation_roles = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'workflow_configurations'
        verbose_name = 'Workflow Configuration'
        verbose_name_plural = 'Workflow Configurations'
    
    def __str__(self):
        return f"Config for {self.stage.name}"


class Deadline(TimestampMixin):
    """
    Deadline tracking for submissions at each stage.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    submission = models.ForeignKey(
        'procurement.Submission',
        on_delete=models.CASCADE,
        related_name='deadlines'
    )
    
    stage = models.ForeignKey(
        WorkflowStage,
        on_delete=models.CASCADE,
        related_name='deadlines'
    )
    
    deadline = models.DateTimeField()
    is_overdue = models.BooleanField(default=False)
    
    # Reminder settings
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Escalation
    escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'submission_deadlines'
        verbose_name = 'Deadline'
        verbose_name_plural = 'Deadlines'
        unique_together = ['submission', 'stage']
    
    def __str__(self):
        return f"{self.submission.tracking_reference} - {self.stage.name}: {self.deadline}"
