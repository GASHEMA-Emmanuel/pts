"""
Division model for PTS.
Represents organizational units: RIDS, HIV, MCCH, Mental Health, Malaria
"""
from django.db import models
from apps.core.models import TimestampMixin


class Division(TimestampMixin):
    """
    Division model representing organizational units within RBC.
    Predefined divisions: RIDS, HIV, MCCH, Mental Health, Malaria
    """
    DIVISION_CHOICES = [
        ('RIDS', 'Research, Innovation and Data Science'),
        ('HIV', 'HIV/AIDS and STIs'),
        ('MCCH', 'Maternal, Child and Community Health'),
        ('Mental Health', 'Mental Health'),
        ('Malaria', 'Malaria and Other Parasitic Diseases'),
        ('NCDs', 'Non-Communicable Diseases'),
        ('Admin', 'Administration'),
        ('Finance', 'Finance'),
        ('Procurement', 'Procurement'),
    ]
    
    id = models.AutoField(primary_key=True, db_column='division_id')
    name = models.CharField(
        max_length=100,
        unique=True,
        db_column='division_name'
    )
    code = models.CharField(max_length=20, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    
    # Contact information
    head_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'divisions'
        verbose_name = 'Division'
        verbose_name_plural = 'Divisions'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate code if not provided
        if not self.code:
            self.code = self.name.upper().replace(' ', '_')[:20]
        super().save(*args, **kwargs)
    
    @property
    def user_count(self):
        """Get the number of users in this division."""
        return self.users.count()
    
    @property
    def submission_count(self):
        """Get the number of submissions from this division."""
        return self.submissions.count()
