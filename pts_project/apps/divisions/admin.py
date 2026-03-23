"""
Admin configuration for divisions app.
"""
from django.contrib import admin
from .models import Division


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'head_name', 'is_active', 'user_count']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Users'
