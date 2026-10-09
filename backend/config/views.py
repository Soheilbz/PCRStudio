from django.db import connection
from django.http import JsonResponse

from accounts.middleware import limiter_client


def liveness(request):
    return JsonResponse({"status": "alive"})


def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        limiter_client().ping()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


def server_error(request):
    return JsonResponse(
        {"code": "internal_error", "detail": "The request could not be completed."}, status=500
    )
