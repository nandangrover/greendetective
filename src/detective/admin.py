from django.contrib import admin
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import InviteCode, InviteRequest, UserProfile, Business, Report, Company
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Count, Q, F
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class InviteMonitoringAdmin(admin.AdminSite):
    site_header = "Detective Admin Panel 💡"
    site_title = "Detective Admin Portal"
    index_title = "Welcome to GreenDetective Admin"

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        # Add any custom URLs here if needed
        return urls

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}

        # User statistics
        user_stats = User.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            staff=Count("id", filter=Q(is_staff=True)),
            superuser=Count("id", filter=Q(is_superuser=True)),
        )

        # Profile statistics
        profile_stats = UserProfile.objects.aggregate(
            total=Count("uuid"),
            verified=Count("uuid", filter=Q(email_verified=True)),
            with_business=Count("uuid", filter=~Q(business=None)),
        )

        # Business statistics
        business_stats = Business.objects.aggregate(
            total=Count("uuid"), by_size=Count("uuid", filter=Q(size=F("size")))
        )

        # Report statistics
        report_stats = Report.objects.aggregate(
            total=Count("uuid"),
            pending=Count("uuid", filter=Q(status=Report.STATUS_PENDING)),
            processing=Count("uuid", filter=Q(status=Report.STATUS_PROCESSING)),
            processed=Count("uuid", filter=Q(status=Report.STATUS_PROCESSED)),
            failed=Count("uuid", filter=Q(status=Report.STATUS_FAILED)),
        )

        # Company statistics
        company_stats = Company.objects.aggregate(
            total=Count("uuid"),
            with_about=Count("uuid", filter=~Q(about_url="")),
            with_summary=Count("uuid", filter=~Q(about_summary="")),
        )

        extra_context.update(
            {
                "user_stats": user_stats,
                "profile_stats": profile_stats,
                "business_stats": business_stats,
                "report_stats": report_stats,
                "company_stats": company_stats,
            }
        )

        return super().index(request, extra_context)


admin_site = InviteMonitoringAdmin(name="admin")


@admin.register(User, site=admin_site)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email")
    readonly_fields = ("date_joined", "last_login")


@admin.register(UserProfile, site=admin_site)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_verified", "business", "created_at")
    list_filter = ("email_verified", "created_at")
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user", "business")


@admin.register(Business, site=admin_site)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "size", "created_at")
    list_filter = ("industry", "size")
    search_fields = ("name", "website")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Report, site=admin_site)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("uuid", "company", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("company__name", "user__username")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("company", "user")


@admin.register(Company, site=admin_site)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "created_at")
    search_fields = ("name", "domain")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InviteCode, site=admin_site)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "status", "created_by", "expires_at", "is_valid")
    list_filter = ("status", "created_by")
    search_fields = ("code", "created_by__username")
    actions = ["send_invite_emails"]

    def is_valid(self, obj):
        return obj.status == InviteCode.STATUS_ACTIVE and (
            not obj.expires_at or obj.expires_at > timezone.now()
        )

    is_valid.boolean = True

    def send_invite_emails(self, request, queryset):
        for invite in queryset:
            if invite.status == InviteCode.STATUS_ACTIVE and (
                not invite.expires_at or invite.expires_at > timezone.now()
            ):
                context = {
                    "code": invite.code,
                    "expires_at": invite.expires_at,
                    "APP_URL": settings.APP_URL,
                    "MEDIA_URL": settings.MEDIA_URL,
                }

                html_message = render_to_string("emails/invite.html", context)
                plain_message = strip_tags(html_message)

                send_mail(
                    subject="Your GreenDetective Invitation",
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[invite.used_by.email] if invite.used_by else [],
                    html_message=html_message,
                    fail_silently=False,
                )

                self.message_user(request, f"Invite emails sent successfully for {invite.code}")

    send_invite_emails.short_description = "Send invite emails to selected codes"


@admin.register(InviteRequest, site=admin_site)
class InviteRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company_name", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "company_name")
    actions = ["approve_requests"]
    list_per_page = 20  # Add pagination for better visibility
    list_select_related = True  # Optimize database queries

    # Add this method to make the action button more prominent
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_approve_button"] = True
        return super().changelist_view(request, extra_context)

    def approve_requests(self, request, queryset):
        from detective.views.invite import generate_invite_code

        for invite_request in queryset:
            invite_request.status = InviteRequest.STATUS_APPROVED
            invite_request.save()

            invite = InviteCode.objects.create(
                code=generate_invite_code(),
                created_by=request.user,
                expires_at=timezone.now() + timezone.timedelta(days=7),
            )

            context = {
                "code": invite.code,
                "expires_at": invite.expires_at,
                "APP_URL": settings.APP_URL,
                "MEDIA_URL": settings.MEDIA_URL,
            }

            html_message = render_to_string("emails/invite.html", context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject="Invitation to join GreenDetective",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[invite_request.email],
                html_message=html_message,
                fail_silently=False,
            )

        self.message_user(request, f"Approved {queryset.count()} requests and sent invites")

    approve_requests.short_description = "Approve selected requests and send invites"

    # Add this line to use the custom template
    change_list_template = "admin/invite_request_change_list.html"
