"""Probe a real SQL conversion failure, then inspect a host-captured database log privately."""
from __future__ import annotations

import argparse
import json
import secrets
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".local/artifacts"
PROBE = ARTIFACTS / "database-log-probe.json"
LOG = ARTIFACTS / "postgres-current.log"


def probe() -> None:
    marker = "synthetic-database-privacy-probe-" + secrets.token_hex(16)
    password = (ROOT / ".local/secrets/db_test_password").read_text().strip()
    with psycopg.connect(host="postgres", dbname="pcrstudio_testdb", user="pcrstudio_test", password=password) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT CAST(%s AS integer)", (marker,))
        except psycopg.errors.InvalidTextRepresentation:
            connection.rollback()
        else:
            raise AssertionError("The database confidentiality probe did not exercise an error")
    PROBE.write_text(json.dumps({"marker": marker, "created_at": time.time(), "sqlstate": "22P02"}) + "\n")
    print("Real database error confidentiality probe executed.")


def verify() -> None:
    evidence = json.loads(PROBE.read_text())
    if not 0 <= time.time() - evidence["created_at"] <= 300:
        raise AssertionError("Database confidentiality evidence is stale; run ./bootstrap check deep")
    if LOG.stat().st_mtime < evidence["created_at"]:
        raise AssertionError("Database logs were captured before the confidentiality probe")
    if evidence["marker"] in LOG.read_text():
        raise AssertionError("Confidential database input appeared in operational logs")
    (ARTIFACTS / "database-log-privacy.json").write_text(json.dumps({"passed": True, "sqlstate": evidence["sqlstate"]}) + "\n")
    print("Database logs exclude the synthetic failed-query input.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "verify"), nargs="?", default="verify")
    action = parser.parse_args().action
    probe() if action == "probe" else verify()
