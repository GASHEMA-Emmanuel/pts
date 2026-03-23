"""
Serializers for Division model.
"""
from rest_framework import serializers
from .models import Division


class DivisionSerializer(serializers.ModelSerializer):
    """Full Division serializer."""
    user_count = serializers.IntegerField(read_only=True)
    submission_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Division
        fields = [
            'id', 'name', 'code', 'description',
            'head_name', 'email', 'phone',
            'is_active', 'user_count', 'submission_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DivisionMinimalSerializer(serializers.ModelSerializer):
    """Minimal Division serializer for nested representations."""
    
    class Meta:
        model = Division
        fields = ['id', 'name', 'code']


class DivisionStatsSerializer(serializers.Serializer):
    """Serializer for division statistics."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    user_count = serializers.IntegerField()
    submission_count = serializers.IntegerField()
    pending_submissions = serializers.IntegerField()
    approved_submissions = serializers.IntegerField()
    total_budget = serializers.DecimalField(max_digits=15, decimal_places=2)
