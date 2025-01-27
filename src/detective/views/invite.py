from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import random
import string
from rest_framework import status
from rest_framework.views import APIView

from detective.models import InviteCode, InviteRequest
from detective.serializers.invite import InviteCodeSerializer, InviteRequestSerializer


def generate_invite_code(length=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


class InviteCodeViewSet(viewsets.ModelViewSet):
    queryset = InviteCode.objects.all()
    serializer_class = InviteCodeSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=["post"])
    def generate(self, request):
        count = int(request.data.get("count", 1))
        expires_in_days = int(request.data.get("expires_in_days", 30))

        print(request.user, "hellooo 1|||")

        invites = []
        for _ in range(count):
            invite = InviteCode.objects.create(
                code=generate_invite_code(),
                created_by=request.user,
                expires_at=timezone.now() + timedelta(days=expires_in_days),
            )
            print(invite, "hellooo||||")
            invites.append(invite)

        serializer = self.get_serializer(invites, many=True)
        return Response(serializer.data)


class InviteRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = InviteRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
