"""Readiness, distinct from process liveness, across the real edge and dependencies."""
import time
from urllib.error import URLError
from urllib.request import urlopen

for _attempt in range(30):
    try:
        with urlopen("http://caddy:8080/health/ready/", timeout=3) as response:
            if response.status == 200:
                print("API, database and limiter are ready through Caddy.")
                break
    except (URLError, TimeoutError):
        pass
    time.sleep(1)
else:
    raise SystemExit("Readiness failed; inspect ./bootstrap status and project service logs.")
