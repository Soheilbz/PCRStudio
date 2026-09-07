#!/usr/bin/env bash
# Canonical Compose launcher for operator scripts on Linux.
set -Eeuo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$root/.env"
if [[ ! -f "$env_file" ]]; then
  echo "PCRStudio .env is missing; run ./bootstrap.sh first" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker is unavailable" >&2
  exit 127
fi

docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    echo "Docker daemon is unavailable" >&2
    exit 1
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    echo "current user cannot access Docker and sudo is unavailable" >&2
    exit 1
  fi
  docker_cmd=(sudo docker)
fi

compose=("${docker_cmd[@]}" compose --env-file "$env_file" -f "$root/compose.yaml")
if [[ "${PCRSTUDIO_PRIVATE_COMPOSE:-0}" == "1" ]]; then
  compose+=( -f "$root/compose.vm.yaml" )
fi
exec "${compose[@]}" "$@"
