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
if [ "${FDH_EXPECT_SYNTHETIC:-0}" = 1 ]; then
  python3 - "$WEB" <<'PYTHON'
import json
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

def get(path):
    with urlopen(sys.argv[1] + "/api/v1" + path, timeout=10) as response:
        return json.load(response)

page = get("/datasets?q=ejecucion")
assert page["total"] == 1, "synthetic budget"
dataset_id = page["items"][0]["id"]
assert get(f"/datasets/{dataset_id}")["provenance"]["total"] > 20
assert get(f"/datasets/{dataset_id}/provenance?page=2")["items"]
for word in ("oculto", "restringido", "denegada"):
    assert get(f"/datasets?q={word}")["total"] == 0, word
runs = get("/runs")["items"]
assert {r["status"] for r in runs} == {"running", "succeeded", "partial", "failed"}
assert any(r["truncated"] for r in runs)
assert any(r["status"] == "failed" and r["persistence_ms"] == 0 for r in runs)
assert any(r["status"] == "running" and r["requests"] is None for r in runs)
try:
    get("/datasets?page_size=101")
except HTTPError as error:
    assert error.code == 422
else:
    raise AssertionError("unbounded page accepted")
print("ok   synthetic catalog and discovery runs through the portal proxy")
PYTHON
fi
echo "smoke test passed"
