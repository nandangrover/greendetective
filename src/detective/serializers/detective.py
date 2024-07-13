from rest_framework import serializers
from detective.models import Company, Report
from detective.tasks import start_detective
from utils import S3Client


class TriggerDetectiveSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    company_domain = serializers.URLField(max_length=200)
    process_urls = serializers.ListField(child=serializers.URLField(), required=False)

    def create_or_get_company(self, validated_data):
        company_name = validated_data.get("company_name")
        company_domain = validated_data.get("company_domain")

        # Check if company already exists
        company = Company.objects.filter(domain=company_domain).first()

        if not company:
            # Create new company if it doesn't exist
            company = Company.objects.create(name=company_name, domain=company_domain)

        return company

    def get_report_url(self, company, validated_data):
        urls_to_process = validated_data.get("process_urls")

        report = Report.objects.filter(company=company, urls=urls_to_process).first()

        user = self.context["request"].user

        if report:
            presigned_url = S3Client().get_report_url(report=report.report_file.name)

            if report.processing:
                start_detective.delay(company.uuid, report.uuid)

            return report.uuid, presigned_url, report.processing
        else:
            # Create a new report if it doesn't exist
            report = Report.objects.create(
                company=company, user=user, urls=urls_to_process
            )
            
            presigned_url = S3Client().get_report_url(report="")

            # start background task to scrape the domain
            start_detective.delay(company.uuid, report.uuid)

            return report.uuid, presigned_url, report.processing

    def validate(self, data):
        company_name = data.get("company_name")
        company_domain = data.get("company_domain")
        process_urls = data.get("process_urls", [])

        if not company_name or not company_domain:
            raise serializers.ValidationError("Company name and domain are required")

        # domain should be a valid URL
        if not company_domain.startswith("https"):
            raise serializers.ValidationError("Invalid domain URL")

        # Max 10 urls can be processed at a time
        if len(process_urls) > 20:
            raise serializers.ValidationError("Max 10 URLs can be processed at a time")

        return data

    def save(self):
        validated_data = self.validated_data

        company = self.create_or_get_company(validated_data)
        report_uuid, s3_url, processing = self.get_report_url(company, validated_data)

        return {
            "company": company.uuid,
            "report": report_uuid,
            "s3_url": s3_url,
            "processing": processing,
        }
