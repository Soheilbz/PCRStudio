import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def secret(name: str, default: str = "") -> str:
    file = os.environ.get(f"{name}_FILE")
    return Path(file).read_text().strip() if file else os.environ.get(name, default)


SECRET_KEY = secret("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY or its private file is required")
MFA_ENCRYPTION_KEY = secret("MFA_ENCRYPTION_KEY")
if not MFA_ENCRYPTION_KEY:
    raise ImproperlyConfigured("MFA_ENCRYPTION_KEY or its private file is required")
try:
    Fernet(MFA_ENCRYPTION_KEY.encode())
except ValueError as error:
    raise ImproperlyConfigured("MFA encryption key has an invalid format") from error
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api,testserver").split(
    ","
)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", f"{FRONTEND_URL},http://127.0.0.1:8080"
).split(",")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "pcrstudio"),
        "USER": os.environ.get("PGUSER", "pcrstudio_runtime"),
        "PASSWORD": secret("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("PGHOST", "postgres"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
if os.environ.get("DATABASE_URL"):
    db = urlparse(os.environ["DATABASE_URL"])
    if db.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("Only PostgreSQL is supported")
    DATABASES["default"].update(
        NAME=unquote(db.path.lstrip("/")),
        USER=unquote(db.username or ""),
        PASSWORD=unquote(db.password or ""),
        HOST=db.hostname or "postgres",
        PORT=str(db.port or 5432),
    )
VALKEY_URL = os.environ.get("VALKEY_URL", "redis://valkey:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": VALKEY_URL,
        "KEY_PREFIX": "pcrstudio-auth",
    }
}
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.mfa",
    "allauth.usersessions",
    "audit",
    "workspaces",
    "projects",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.logging.OperationalLogMiddleware",
    "accounts.middleware.PrivateResponseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "allauth.usersessions.middleware.UserSessionsMiddleware",
    "accounts.middleware.MandatoryMFAMiddleware",
    "accounts.middleware.AuthLimiterMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = FRONTEND_URL.startswith("https://")
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000 if SESSION_COOKIE_SECURE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SESSION_COOKIE_SECURE
SECURE_HSTS_PRELOAD = SESSION_COOKIE_SECURE
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_REAUTHENTICATION_TIMEOUT = 300
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
MFA_ADAPTER = "accounts.adapters.MFAAdapter"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ["browser"]
HEADLESS_SERVE_SPECIFICATION = True
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{FRONTEND_URL}/account/verify-email/{{key}}",
    "account_reset_password_from_key": f"{FRONTEND_URL}/account/password/reset/key/{{key}}",
    "account_signup": f"{FRONTEND_URL}/account/signup",
}
USERSESSIONS_TRACK_ACTIVITY = True
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "mailpit")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = secret("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = 10
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "PCRStudio <noreply@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["accounts.permissions.VerifiedAccount"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "config.pagination.PrivatePagination",
    "PAGE_SIZE": 30,
    "EXCEPTION_HANDLER": "config.errors.exception_handler",
    "UNAUTHENTICATED_USER": None,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "PCRStudio private platform",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Our PATCH handlers validate explicit mutation serializers without partial=True;
    # expected version (or the new membership role) is required on every request.
    "COMPONENT_SPLIT_PATCH": False,
    "ENUM_NAME_OVERRIDES": {
        "WorkspaceRoleEnum": [("owner", "Owner"), ("member", "Member")],
        "ProjectRoleEnum": ["owner", "editor", "viewer"],
    },
}
# Omit request/payload-bearing framework logging, including exception traces and URLs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {"safe_json": {"()": "config.logging.SafeJSONFormatter"}},
    "handlers": {
        "null": {"class": "logging.NullHandler"},
        "safe": {"class": "logging.StreamHandler", "formatter": "safe_json"},
    },
    "root": {"handlers": ["null"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["null"], "propagate": False},
        "platform.operations": {"handlers": ["safe"], "level": "INFO", "propagate": False},
    },
}
