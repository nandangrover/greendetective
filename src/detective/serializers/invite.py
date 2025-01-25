from rest_framework import serializers
from detective.models import InviteCode
from django.contrib.auth import get_user_model

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class InviteCodeSerializer(serializers.ModelSerializer):
    created_by = UserBasicSerializer(read_only=True)
    used_by = UserBasicSerializer(read_only=True)
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = InviteCode
        fields = [
            "uuid",
            "code",
            "status",
            "created_by",
            "used_by",
            "expires_at",
            "created_at",
            "used_at",
            "is_valid",
        ]
        read_only_fields = [
            "uuid",
            "code",
            "created_by",
            "used_by",
            "created_at",
            "used_at",
        ]

    def get_is_valid(self, obj):
        """
        Check if the invite code is still valid (active and not expired)
        """
        from django.utils import timezone

        if obj.status != InviteCode.STATUS_ACTIVE:
            return False
        if obj.expires_at and obj.expires_at < timezone.now():
            return False
        return True
