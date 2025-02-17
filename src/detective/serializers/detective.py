from rest_framework import serializers
from detective.models import Company, Report, UserProfile
from detective.tasks import start_detective
from utils import S3Client
from datetime import timedelta
from django.utils import timezone
from detective.serializers.report import ReportSerializer


class TriggerDetectiveSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    company_domain = serializers.URLField(max_length=200)
    about_url = serializers.URLField(max_length=200, required=False)
    process_urls = serializers.ListField(child=serializers.URLField(), required=False)

    def create_or_get_company(self, validated_data):
        company_name = validated_data.get("company_name")
        company_domain = validated_data.get("company_domain")
        about_url = validated_data.get("about_url", "")

        # Check if company already exists
        company = Company.objects.filter(domain=company_domain).first()

        if not company:
            # Create new company if it doesn't exist
            company = Company.objects.create(
                name=company_name, domain=company_domain, about_url=about_url
            )

        if company and not company.about_url and about_url:
            company.about_url = about_url
            company.save()

        return company

    def get_report_url(self, company, validated_data):
        urls_to_process = validated_data.get("process_urls")

        report = (
            Report.objects.filter(company=company, urls=urls_to_process)
            .order_by("-created_at")
            .first()
        )

        user = self.context["request"].user

        # Return existing report if it exists and created within the last week
        if report and report.created_at > timezone.now() - timedelta(days=7):
            presigned_url = S3Client().get_report_url(report=report.report_file.name)
            return (
                report.uuid,
                presigned_url,
                report.status == Report.STATUS_PENDING
                or report.status == Report.STATUS_PROCESSING,
            )
        else:
            if not urls_to_process:
                urls_to_process = []
            # Create a new report
            report = Report.objects.create(
                company=company, user=user, urls=urls_to_process, status=Report.STATUS_PENDING
            )

            presigned_url = S3Client().get_report_url(report="")

            # start background task to scrape the domain
            start_detective.delay(str(company.uuid), str(report.uuid))

            return report.uuid, presigned_url, True

    def validate(self, data):
        company_name = data.get("company_name")
        company_domain = data.get("company_domain")
        process_urls = data.get("process_urls", [])
        user = self.context["request"].user

        if not company_name or not company_domain:
            raise serializers.ValidationError("Company name and domain are required")

        # domain should be a valid URL
        if not company_domain.startswith("https"):
            raise serializers.ValidationError("Invalid domain URL")

        # Max 20 urls can be processed at a time
        if len(process_urls) > 20:
            raise serializers.ValidationError("Max 20 URLs can be processed at a time")

        # Check if user's business can generate more reports
        profile = UserProfile.objects.get(user=user)
        if profile.business and not profile.business.can_generate_report():
            raise serializers.ValidationError(
                "Your business has reached its report limit for this plan"
            )

        return data

    def save(self):
        validated_data = self.validated_data
        user = self.context["request"].user
        profile = UserProfile.objects.get(user=user)

        if not profile.business.can_generate_report():
            raise serializers.ValidationError(
                "Your business has reached its report limit for this plan"
            )

        company = self.create_or_get_company(validated_data)
        report_uuid, s3_url, processing = self.get_report_url(company, validated_data)

        # Get report
        report = Report.objects.get(uuid=report_uuid)

        return {
            "company": company.uuid,
            "report": report_uuid,
            "s3_url": s3_url,
            "processing": processing,
            "status": report.status,
        }
