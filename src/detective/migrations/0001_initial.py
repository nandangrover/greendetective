# Generated by Django 5.0.6 on 2025-01-29 19:12

import custom_storages
import detective.models.report
import django.contrib.postgres.fields
import django.db.models.deletion
import pgvector.django.vector
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('domain', models.CharField(max_length=255, unique=True)),
                ('about_url', models.URLField(default='')),
                ('about_raw', models.TextField(default='')),
                ('about_summary', models.TextField(default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='InviteRequest',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('company_name', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='PaymentPlan',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('name', models.CharField(choices=[('BETA', 'Beta Plan'), ('BASIC', 'Basic Plan'), ('PRO', 'Pro Plan'), ('ENTERPRISE', 'Enterprise Plan')], default='BETA', max_length=20, unique=True)),
                ('max_reports', models.PositiveIntegerField(default=3)),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=6)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('used', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='InviteCode',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=20, unique=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('used', 'Used'), ('expired', 'Expired')], default='active', max_length=20)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_invites', to=settings.AUTH_USER_MODEL)),
                ('used_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='used_invite', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Business',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('website', models.URLField(blank=True, max_length=255)),
                ('industry', models.CharField(max_length=100)),
                ('size', models.CharField(choices=[('1-10', '1-10 employees'), ('11-50', '11-50 employees'), ('51-200', '51-200 employees'), ('201-500', '201-500 employees'), ('501+', '501+ employees')], max_length=20)),
                ('reports_generated', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment_plan', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='detective.paymentplan')),
            ],
        ),
        migrations.CreateModel(
            name='Report',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('urls', django.contrib.postgres.fields.ArrayField(base_field=models.URLField(max_length=2048), default=list, size=20)),
                ('processed', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('processed', 'Processed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('report_file', models.FileField(blank=True, null=True, storage=custom_storages.ReportStorage(), upload_to=detective.models.report.get_upload_path)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='detective.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'reports',
            },
        ),
        migrations.CreateModel(
            name='Staging',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('url', models.URLField(max_length=2048)),
                ('raw', models.TextField()),
                ('processed', models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('PROCESSED', 'Processed'), ('FAILED', 'Failed')], default='PENDING', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('defunct', models.BooleanField(default=False)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='detective.company')),
            ],
        ),
        migrations.CreateModel(
            name='Run',
            fields=[
                ('run_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('run_oa_id', models.CharField(max_length=255, unique=True)),
                ('thread_oa_id', models.CharField(max_length=255, unique=True)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('in_progress', 'In Progress'), ('requires_action', 'Requires Action'), ('cancelling', 'Cancelling'), ('cancelled', 'Cancelled'), ('failed', 'Failed'), ('completed', 'Completed'), ('expired', 'Expired')], max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('failed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True, null=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('staging', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='detective.staging')),
            ],
        ),
        migrations.CreateModel(
            name='RawStatistics',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('claim', models.TextField(default=None)),
                ('evaluation', models.TextField()),
                ('score', models.FloatField()),
                ('score_breakdown', models.JSONField(blank=True, null=True)),
                ('category', models.CharField(blank=True, choices=[('environmental', 'Environmental'), ('social', 'Social'), ('governance', 'Governance'), ('product', 'Product'), ('general', 'General')], default='general', max_length=50, null=True)),
                ('justification', models.JSONField(blank=True, null=True)),
                ('recommendations', models.TextField(blank=True, null=True)),
                ('processed', models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('PROCESSED', 'Processed'), ('FAILED', 'Failed')], default='PENDING', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('defunct', models.BooleanField(default=False)),
                ('comparison_analysis', models.JSONField(blank=True, help_text='Raw JSON response from claim comparison analysis', null=True)),
                ('embedding', pgvector.django.vector.VectorField(blank=True, dimensions=512, help_text='Vector embeddings for evaluation text', null=True)),
                ('company', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='detective.company')),
                ('staging', models.ManyToManyField(to='detective.staging')),
            ],
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('job_title', models.CharField(max_length=100)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('email_verified', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='detective.business')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
