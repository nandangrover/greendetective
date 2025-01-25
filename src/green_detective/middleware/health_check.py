from rest_framework import status
from django.http import HttpResponse


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/health-check":
            return HttpResponse("ok", status=status.HTTP_200_OK)
        return self.get_response(request)
