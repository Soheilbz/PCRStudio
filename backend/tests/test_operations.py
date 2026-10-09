import json
import logging
from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from config.logging import OperationalLogMiddleware, SafeJSONFormatter
from config.notifications import notify_on_commit


def test_operational_logs_exclude_payload_path_and_query():
    request = RequestFactory().post(
        "/api/v1/projects/synthetic-private-id/?secret=private", {"name": "private-name"}
    )
    response = HttpResponse(status=409)
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("platform.operations")
    handler = Capture()
    logger.addHandler(handler)
    try:
        OperationalLogMiddleware(lambda _: response)(request)
    finally:
        logger.removeHandler(handler)
    result = SafeJSONFormatter().format(records[-1])
    data = json.loads(result)
    assert data["route"] == "unresolved"
    assert data["status"] == 409
    assert data["error_code"] == "conflict"
    assert "private" not in result
    assert "synthetic" not in result
    assert "X-Request-ID" in response


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure", [SMTPException("private-email@example.test"), OSError("secret")]
)
def test_notification_failure_log_has_only_operational_kind(
    failure, django_capture_on_commit_callbacks
):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("platform.operations")
    handler = Capture()
    logger.addHandler(handler)
    try:
        with (
            patch("config.notifications.send_mail", side_effect=failure),
            django_capture_on_commit_callbacks(execute=True),
        ):
            notify_on_commit(
                "workspace_invitation", "Synthetic subject", "secret token", "private@example.test"
            )
    finally:
        logger.removeHandler(handler)
    assert len(records) == 1
    assert json.loads(SafeJSONFormatter().format(records[0])) == {
        "event": "notification_failed",
        "kind": "workspace_invitation",
    }
    assert records[0].exc_info is None
