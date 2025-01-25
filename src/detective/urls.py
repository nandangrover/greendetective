from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SignupView,
    LoginView,
    TriggerDetectiveView,
    ReportListView,
    ReportDetailView,
    InviteCodeViewSet,
    VerifyEmailView,
    ResendVerificationView,
)

router = DefaultRouter()
router.register(r"invites", InviteCodeViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),
    path("trigger_detective/", TriggerDetectiveView.as_view(), name="trigger_detective"),
    path("reports/", ReportListView.as_view(), name="report-list"),
    path("report/<uuid:uuid>/", ReportDetailView.as_view(), name="report-detail"),
]
