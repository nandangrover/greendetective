from rest_framework import status
from django.http import JsonResponse
from django.db import connection
from redis import Redis
from django.conf import settings
import socket


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ["/health", "/health/"]:
            health_status = {
                "status": "ok",
            }
            http_status = status.HTTP_200_OK

            return JsonResponse(health_status, status=http_status)

        return self.get_response(request)
