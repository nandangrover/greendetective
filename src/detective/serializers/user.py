from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from detective.models import (
    Company,
    Report,
    Business,
    UserProfile,
    InviteCode,
    EmailVerificationToken,
)
from django.utils import timezone
from detective.utils.email import EmailService


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ("name", "website", "industry", "size")


class UserProfileSerializer(serializers.ModelSerializer):
    business = BusinessSerializer(required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = ("job_title", "phone", "business")


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()
    invite_code = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "profile", "invite_code")
        extra_kwargs = {"password": {"write_only": True}, "email": {"required": True}}

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_invite_code(self, value):
        try:
            invite = InviteCode.objects.get(
                code=value, status=InviteCode.STATUS_ACTIVE, expires_at__gt=timezone.now()
            )
            return invite
        except InviteCode.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired invite code")

    def create(self, validated_data):
        invite_code = validated_data.pop("invite_code")
        profile_data = validated_data.pop("profile", {})
        business_data = profile_data.pop("business", None)

        # Create user first
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )

        # Create business if data is provided
        business = None
        if business_data:
            business = Business.objects.create(**business_data)

        # Update profile
        user.profile.job_title = profile_data.get("job_title", "")
        user.profile.phone = profile_data.get("phone", "")
        if business:
            user.profile.business = business
        user.profile.save()

        # Mark invite code as used
        invite_code.status = InviteCode.STATUS_USED
        invite_code.used_by = user
        invite_code.used_at = timezone.now()
        invite_code.save()

        # Create verification token and send email
        verification_token = EmailVerificationToken.objects.create(user=user)
        EmailService.send_verification_email(user, verification_token.token)

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField()

    def validate(self, data):
        username = data.get("username")
        email = data.get("email")

        if not username and not email:
            raise serializers.ValidationError("A username or email is required to login")

        return data
