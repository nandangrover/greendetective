from django.urls import path
from .views import SignupView, LoginView, TriggerDetectiveView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    
    path('trigger_detective/', TriggerDetectiveView.as_view(), name='trigger_detective'),
]