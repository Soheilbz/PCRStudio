from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.policy import mfa_authenticated, mfa_enabled, mfa_required, verified
from accounts.serializers import CSRFSerializer, MeSerializer


class CSRFView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=CSRFSerializer, auth=[])
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class MeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        if not verified(request.user):
            return Response(
                {
                    "code": "authentication_required",
                    "detail": "Sign in with a verified email account.",
                },
                status=401,
            )
        user = request.user
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "email_verified": True,
                "mfa_enabled": mfa_enabled(user),
                "mfa_required": mfa_required(user),
                "mfa_authenticated": mfa_authenticated(request),
            }
        )
