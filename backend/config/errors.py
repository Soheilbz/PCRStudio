from rest_framework.exceptions import APIException


class DomainError(APIException):
    status_code = 400
    default_code = "invalid_request"

    def __init__(self, code: str, detail: str, status: int = 400):
        self.status_code = status
        super().__init__(detail, code)


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)
    if response is not None:
        code = getattr(exc, "default_code", "invalid_request")
        if isinstance(exc, DomainError):
            code = exc.get_codes()
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        # Serializer errors identify fields but never echo supplied values.
        if detail is None:
            detail = "Check the supplied fields."
        response.data = {"code": code, "detail": str(detail)}
    return response
