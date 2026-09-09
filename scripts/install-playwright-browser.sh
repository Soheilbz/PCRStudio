#!/usr/bin/env bash
set -Eeuo pipefail

# Browser archives are immutable for a locked Playwright version, but the
# download path is still an external CDN. Retry only this transport boundary;
# the final attempt remains fatal so a missing browser can never be mistaken
# for a green browser qualification.
for attempt in 1 2 3; do
  echo "Installing locked Chromium (attempt ${attempt}/3)"
  if pnpm --filter web exec playwright install --with-deps chromium; then
    exit 0
  fi
  status=$?
  if (( attempt == 3 )); then
    exit "$status"
  fi
  delay=$((attempt * 5))
  echo "Chromium installation failed at the external browser/OS-package boundary; retrying in ${delay}s" >&2
  sleep "$delay"
done
