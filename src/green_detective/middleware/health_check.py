from rest_framework import status
from django.http import JsonResponse
from django.db import connection


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/health-check":
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return JsonResponse({"status": "ok"})
            except Exception as e:
                return JsonResponse({"status": "error", "message": str(e)}, status=500)
        return self.get_response(request)
