"""Emit bounded server events without request URIs, exception values or traceback locals."""
from __future__ import annotations

import logging

from gunicorn.glogging import Logger


class ConfidentialServerFilter(logging.Filter):
    EVENTS = {
        "Starting gunicorn %s": "server.start",
        "Listening at: %s (%s)": "server.listen",
        "Using worker: %s": "server.worker_mode",
        "Booting worker with pid: %s": "worker.start",
        "Worker exiting (pid: %s)": "worker.exit",
        "WORKER TIMEOUT (pid:%s)": "worker.timeout",
        "Worker failed to boot.": "worker.boot_failed",
        "Handling signal: %s": "server.signal",
        "Shutting down: %s": "server.shutdown",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.EVENTS.get(str(record.msg), "server.event")
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class SafeLogger(Logger):
    error_fmt = '{"source":"gunicorn","event":"%(message)s","level":"%(levelname)s","process":%(process)d}'

    def setup(self, cfg) -> None:
        super().setup(cfg)
        for current in tuple(self.error_log.filters):
            if isinstance(current, ConfidentialServerFilter):
                self.error_log.removeFilter(current)
        self.error_log.addFilter(ConfidentialServerFilter())
