from rest_framework import status, generics, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from ..models import Report
from ..serializers import ReportSerializer
from ..tasks import start_detective


class ReportListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer

    def get_queryset(self):
        return Report.objects.filter(user=self.request.user).order_by("-created_at")


class ReportDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        return Report.objects.filter(user=self.request.user)


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set initial status
        report = serializer.save(user=request.user, status=Report.STATUS_PENDING)

        # Start the detective process
        start_detective.delay(str(report.company.uuid), str(report.uuid))

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        report = self.get_object()
        return Response(
            {
                "status": report.status,
                "status_display": report.get_status_display(),
                "processed": report.processed,  # For backwards compatibility
                "has_report": bool(report.report_file),
            }
        )

    def get_queryset(self):
        queryset = Report.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset.order_by("-created_at")
