from django.urls import path
from .views import SignupView, LoginView, TriggerDetectiveView, ReportListView, ReportDetailView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    
    path('trigger_detective/', TriggerDetectiveView.as_view(), name='trigger_detective'),
    path('reports/', ReportListView.as_view(), name='report-list'),
    path('reports/<uuid:uuid>/', ReportDetailView.as_view(), name='report-detail'),
]