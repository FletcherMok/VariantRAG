#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results/audit
npm audit --prefix frontend --json > results/audit/npm.json
for lock in requirements.lock requirements-dev.lock requirements-catt.lock requirements-mutalyzer.lock; do
  uv tool run pip-audit==2.10.1 --no-deps --disable-pip -r "$lock" -f json -o "results/audit/${lock}.json"
done
# This optional environment has an acknowledged upstream advisory. Preserve its
# failing status in a report rather than disguising it as a clean scan.
optional_status=0
uv tool run pip-audit==2.10.1 --no-deps --disable-pip -r requirements-research.lock -f json -o results/audit/optional-research.json || optional_status=$?
echo "Optional research audit exit status: $optional_status (review SECURITY.md and report)"
gitleaks git . --redact --report-format json --report-path results/audit/secrets-history.json
echo 'History scanned. Also inspect the staged tree before committing.'
exit "$optional_status"
