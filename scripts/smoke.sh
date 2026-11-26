#!/usr/bin/env bash
# Smoke test of the running Compose environment. Only talks to the local machine.
set -euo pipefail

API="http://127.0.0.1:${FDH_API_PORT:-8000}"
WEB="http://127.0.0.1:${FDH_WEB_PORT:-8080}"
fail() { echo "FAIL $1" >&2; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" || true; }

[ "$(curl -fsS --max-time 10 "$API/health")" = '{"status":"ok"}' ] || fail "API health"
echo "ok   API health"
[ "$(curl -fsS --max-time 10 "$WEB/health")" = '{"status":"ok"}' ] || fail "health through the portal"
echo "ok   health through the portal proxy"
curl -fsS --max-time 10 "$WEB/" | grep -q '<div id="root">' || fail "portal page"
echo "ok   portal page"
headers="$(curl -fsSI --max-time 10 "$WEB/")"
for header in content-security-policy x-content-type-options referrer-policy; do
  grep -qi "^$header:" <<<"$headers" || fail "missing header $header"
done
echo "ok   security headers"
[ "$(status -H 'Host: attacker.example' "$API/health")" = "400" ] || fail "API accepted a foreign Host"
[ "$(status -H 'Host: attacker.example' "$WEB/")" = "000" ] || fail "portal answered a foreign Host"
echo "ok   foreign Host rejected"
[ "$(status -X POST "$API/health")" = "405" ] || fail "API accepted a write method"
echo "ok   write method rejected"
echo "smoke test passed"
