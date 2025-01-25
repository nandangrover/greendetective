from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from ..serializers import TriggerDetectiveSerializer


class TriggerDetectiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TriggerDetectiveSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            data = serializer.save()
            return Response(data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
