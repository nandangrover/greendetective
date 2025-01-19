from rest_framework import serializers
from detective.models import Report

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['uuid', 'company', 'user', 'urls', 'processing', 'report_file', 'created_at', 'updated_at']