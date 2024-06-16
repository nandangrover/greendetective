from rest_framework import serializers
from detective.models import Company, Report

class TriggerDetectiveSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    company_domain = serializers.URLField(max_length=200)

    def create_or_get_company(self, validated_data):
        company_name = validated_data.get('company_name')
        company_domain = validated_data.get('company_domain')

        # Check if company already exists
        company = Company.objects.filter(name=company_name, domain=company_domain).first()

        if not company:
            # Create new company if it doesn't exist
            company = Company.objects.create(name=company_name, domain=company_domain)

        return company

    def get_report_url(self, company):
        # Check if a report already exists for the company
        report = Report.objects.filter(company_uuid=company).first()

        if report:
            return report.uuid, report.s3_url, report.processing
        else:
            # Create a new report if it doesn't exist
            report = Report.objects.create(company_uuid=company, user_id=self.context['request'].user)
            return report.uuid, None, report.processing

    def validate(self, data):
        company_name = data.get('company_name')
        company_domain = data.get('company_domain')

        if not company_name or not company_domain:
            raise serializers.ValidationError("Company name and domain are required")
        
        # domain should be a valid URL
        if not company_domain.startswith("https"):
            raise serializers.ValidationError("Invalid domain URL")

        return data

    def save(self):
        validated_data = self.validated_data
        user = validated_data.get('user')

        company = self.create_or_get_company(validated_data)
        report_uuid, s3_url, processing = self.get_report_url(company)

        return {
            "company": company.uuid,
            "report": report_uuid,
            "s3_url": s3_url,
            "processing": processing,
        }
