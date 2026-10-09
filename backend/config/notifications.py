import logging
from smtplib import SMTPException
from typing import Literal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction


def notify_on_commit(
    kind: Literal["workspace_invitation", "project_recovery"],
    subject: str,
    body: str,
    recipient: str,
) -> None:
    def deliver() -> None:
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
        except (SMTPException, OSError):
            # The domain change is already committed. Surface delivery failure to
            # operators without changing its result or logging an SMTP payload.
            logging.getLogger("platform.operations").warning(
                "notification_failed",
                extra={"safe_fields": {"event": "notification_failed", "kind": kind}},
            )

    transaction.on_commit(deliver)
