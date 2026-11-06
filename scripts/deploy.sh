#!/usr/bin/env bash
# Production deploy for the HRMS app inside a Frappe bench.
# The workflow pulls this repo first. This script migrates, builds assets, and restarts.
# Secrets stay in sites/<site>/site_config.json on the server. Do not commit that file.

set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-/home/wngelique/frappe-bench}"
SITE="${BENCH_SITE:-mysite.local}"

cd "$BENCH_ROOT"

export PATH="${HOME}/.local/bin:${BENCH_ROOT}/env/bin:${PATH}"

if [[ -x "${HOME}/.local/bin/bench" ]]; then
  BENCH="${HOME}/.local/bin/bench"
elif command -v bench >/dev/null 2>&1; then
  BENCH="$(command -v bench)"
else
  echo "bench was not found on PATH for user $(whoami)."
  echo "Install bench for this user, or run the GitHub runner as the bench owner."
  exit 1
fi

if [[ ! -d "$BENCH_ROOT/sites/$SITE" ]]; then
  echo "Site $SITE was not found under $BENCH_ROOT/sites."
  echo "Set the GitHub variable BENCH_SITE to the real site name."
  exit 1
fi

echo "Migrating $SITE"
"$BENCH" --site "$SITE" migrate

echo "Building hrms assets"
"$BENCH" build --app hrms

echo "Clearing cache"
"$BENCH" --site "$SITE" clear-cache

echo "Restarting bench"
"$BENCH" restart

echo "Deploy finished for $SITE in $BENCH_ROOT"
