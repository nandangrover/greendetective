from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from detective.models import EmailVerificationToken
from detective.utils.email import EmailService


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")

        verification = get_object_or_404(EmailVerificationToken, token=token)

        if not verification.is_valid:
            return Response(
                {"error": "Invalid or expired verification token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = verification.user

        # Mark email as verified
        user.profile.email_verified = True
        user.profile.save()

        # Mark token as used
        verification.used = True
        verification.save()

        # Send welcome email
        EmailService.send_welcome_email(user)

        return Response({"message": "Email verified successfully"})


class ResendVerificationView(APIView):
    def post(self, request):
        user = request.user

        if user.profile.email_verified:
            return Response(
                {"message": "Email already verified"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Create new verification token
        verification_token = EmailVerificationToken.objects.create(user=user)

        # Send verification email
        EmailService.send_verification_email(user, verification_token.token)

        return Response({"message": "Verification email sent"})
