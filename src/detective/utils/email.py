from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


class EmailService:
    @staticmethod
    def send_verification_email(user, token):
        verification_url = f"{settings.FRONTEND_URL}/api/v1/detective/verify-email/{token}"

        context = {
            "user": user,
            "verification_url": verification_url,
            "expiry_days": 3,
            "APP_URL": settings.APP_URL,
            "MEDIA_URL": settings.MEDIA_URL,
        }

        html_message = render_to_string("emails/verify_email.html", context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject="Verify your email address",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

    @staticmethod
    def send_welcome_email(user):
        context = {
            "user": user,
            "APP_URL": settings.APP_URL,
            "MEDIA_URL": settings.MEDIA_URL,
        }

        html_message = render_to_string("emails/welcome.html", context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject="Welcome to GreenDetective",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
