import json
import logging
import time
import uuid


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        # Only fixed operational dictionaries reach this handler. Messages and
        # exception details are deliberately never formatted.
        fields = getattr(record, "safe_fields", {})
        return json.dumps({"event": "http_request", **fields}, separators=(",", ":"))


class OperationalLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("platform.operations")

    def __call__(self, request):
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        response = self.get_response(request)
        match = getattr(request, "resolver_match", None)
        template = getattr(match, "route", None) or "unresolved"
        # route is defined in source, never the user-supplied path or query string.
        self.logger.info(
            "http_request",
            extra={
                "safe_fields": {
                    "request_id": request_id,
                    "route": template,
                    "method": request.method
                    if request.method
                    in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                    else "OTHER",
                    "status": response.status_code,
                    "error_code": {
                        400: "invalid_request",
                        401: "authentication_required",
                        403: "forbidden",
                        404: "not_found",
                        409: "conflict",
                        429: "rate_limited",
                        500: "internal_error",
                        503: "unavailable",
                    }.get(response.status_code),
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                }
            },
        )
        response["X-Request-ID"] = request_id
        return response
