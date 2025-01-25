from rest_framework import serializers
from detective.models import Report, Staging, RawStatistics
from utils import S3Client


class ReportSerializer(serializers.ModelSerializer):
    s3_url = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    company_domain = serializers.SerializerMethodField()
    eta_minutes = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = [
            "uuid",
            "company",
            "company_name",
            "company_domain",
            "user",
            "urls",
            "processed",  # Keep for backwards compatibility
            "status",
            "status_display",
            "report_file",
            "created_at",
            "updated_at",
            "s3_url",
            "eta_minutes",
        ]
        read_only_fields = ["processed", "status", "report_file"]

    def get_s3_url(self, obj):
        if obj.report_file:
            return S3Client().get_report_url(report=obj.report_file.name)
        return ""

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_company_domain(self, obj):
        return obj.company.domain if obj.company else None

    def get_eta_minutes(self, obj):
        if obj.status == Report.STATUS_PROCESSED:
            return 0

        # Calculate remaining tasks
        pending_staging = Staging.objects.filter(
            company_id=obj.company_id, processed=Staging.STATUS_PENDING, defunct=False
        ).count()

        processing_staging = Staging.objects.filter(
            company_id=obj.company_id,
            processed=Staging.STATUS_PROCESSING,
            defunct=False,
        ).count()

        pending_stats = RawStatistics.objects.filter(
            company_id=obj.company_id,
            processed=RawStatistics.STATUS_PENDING,
            defunct=False,
        ).count()

        processing_stats = RawStatistics.objects.filter(
            company_id=obj.company_id,
            processed=RawStatistics.STATUS_PROCESSING,
            defunct=False,
        ).count()

        # Rough estimates:
        # - Each staging record takes ~30 seconds
        # - Each stat record takes ~30 seconds
        # - Add 5 minutes buffer for scraping and report generation
        eta_minutes = (
            (pending_staging + processing_staging) * 0.5  # Staging processing time
            + (pending_stats + processing_stats) * 0.5  # Stats processing time
            + 5  # Buffer time
        )

        return max(1, eta_minutes)  # Return at least 1 minute if processing
