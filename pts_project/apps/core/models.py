"""
Base model mixins for PTS.
Provides common functionality across all models.
"""
import uuid
from django.db import models
from django.utils import timezone


class UUIDMixin(models.Model):
    """Mixin that adds UUID as primary key."""
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    """Mixin that adds created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Mixin for soft delete functionality.
    Records are marked as deleted instead of being removed from the database.
    """
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
    
    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class AuditMixin(models.Model):
    """
    Mixin for audit trail functionality.
    Tracks who created and last modified the record.
    """
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    modified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_modified'
    )
    
    class Meta:
        abstract = True


class BaseModel(UUIDMixin, TimestampMixin):
    """
    Base model combining UUID and Timestamp mixins.
    Use this as the base for most PTS models.
    """
    class Meta:
        abstract = True


class AuditableModel(BaseModel, AuditMixin, SoftDeleteMixin):
    """
    Full-featured base model with UUID, timestamps, audit trail, and soft delete.
    Use this for critical models requiring complete audit functionality.
    """
    class Meta:
        abstract = True
