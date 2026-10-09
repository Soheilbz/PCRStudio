from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator
from cryptography.fernet import Fernet
from django.conf import settings

from accounts.policy import mfa_required


class AccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        return super().clean_email(email).lower()


class MFAAdapter(DefaultMFAAdapter):
    def _cipher(self):
        return Fernet(settings.MFA_ENCRYPTION_KEY.encode())

    def encrypt(self, text: str) -> str:
        return self._cipher().encrypt(text.encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        return self._cipher().decrypt(encrypted_text.encode()).decode()

    def can_delete_authenticator(self, authenticator):
        if authenticator.type == Authenticator.Type.TOTP and mfa_required(authenticator.user):
            return False
        return super().can_delete_authenticator(authenticator)
