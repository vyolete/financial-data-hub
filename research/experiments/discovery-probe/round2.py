"""Second live round: Socrata cursor paging, World Bank Data360 and a Data Catalog retest.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/round2.py socrata
    python3 -I research/experiments/discovery-probe/round2.py data360

Reuses the sanitized recorder of probe.py and adds POST support. Only status,
timing, size, body hash, JSON schema and aggregate counts are stored. No
credentials are used. The only retries are on HTTP 429, honouring Retry-After.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probe", HERE / "probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

DATA360 = "https://data360api.worldbank.org/data360"
OPENAPI = "https://raw.githubusercontent.com/worldbank/open-api-specs/main/Data360%20Open_API.json"


def post(probe_id, purpose, url, body, keep_schema=False, summarize=None):
    """Send one JSON POST (or a raw string body) and record sanitized evidence."""
    if len(probe.records) >= probe.MAX_REQUESTS:
        raise RuntimeError("request budget exhausted")
    payload = body if isinstance(body, str) else json.dumps(body)
    record = {"id": probe_id, "purpose": purpose, "method": "POST", "url": url,
              "request_body": body, "utc": probe.utc_now()}
    request = urllib.request.Request(
        url, data=payload.encode(), method="POST",
        headers={"User-Agent": probe.USER_AGENT, "Content-Type": "application/json"})
    started = time.monotonic()
    raw, headers = b"", {}
    try:
        with urllib.request.urlopen(request, timeout=probe.TIMEOUT_S) as response:
            record["status"], headers = response.status, response.headers
            raw = response.read(probe.MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        record["status"], headers = error.code, error.headers
        raw = error.read(probe.MAX_BYTES + 1)
    except Exception as error:  # network failures are evidence, not crashes
        record["status"] = None
        record["transport_error"] = probe.scrub(f"{type(error).__name__}: {error}")[:300]
    record["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    record["bytes"] = len(raw)
    record["content_type"] = headers.get("Content-Type") if headers else None
    record["retry_after"] = headers.get("Retry-After") if headers else None
    record["body_sha256"] = hashlib.sha256(raw).hexdigest() if raw else None
    data = None
    try:
        data = json.loads(raw.decode("utf-8-sig"))
        record["json"] = True
    except (ValueError, UnicodeDecodeError):
        record["json"] = False
    if record["status"] and record["status"] >= 400:
        record["error_excerpt"] = probe.scrub(raw.decode("utf-8", "replace"))[:300]
    if data is not None:
        if keep_schema:
            record["schema"] = {k: sorted(v) for k, v in sorted(probe.schema(data).items())}
        if summarize:
            try:
                record["summary"] = summarize(data)
            except Exception as error:
                record["summary_error"] = f"{type(error).__name__}: {error}"[:200]
    probe.records.append(record)
    print(f"{probe_id:6} {record['status']} {record['elapsed_ms']:>6} ms {record['bytes']:>8} B  {purpose}")
    time.sleep(probe.DELAY_S)
    return record, data


def flatten(item):
    """Flatten one level of nested objects: {'a': {'b': 1}} -> {'a.b': 1}."""
    out = {}
    for key, value in item.items():
        if isinstance(value, dict):
            out.update({f"{key}.{k}": v for k, v in value.items()})
        else:
            out[key] = value
    return out


def search_summary(data):
    if not isinstance(data, dict) or "value" not in data:
        return {"body_excerpt": probe.scrub(json.dumps(data))[:300]}
    items = [flatten(i) for i in data["value"]]
    keys = sorted({k for i in items for k in i})
    return {
        "top_level_keys": sorted(data),
        "count": data.get("@odata.count"),
        "returned": len(items),
        "unique_ids": len({i.get("series_description.idno") for i in items}),
        "facets": data.get("@search.facets"),
        "filled_fields": {k: sum(probe.filled(i.get(k)) for i in items) for k in keys},
        "types": probe.short_values(items, lambda i: i.get("type")),
    }


def ids(data):
    return [flatten(i).get("series_description.idno") for i in (data or {}).get("value", [])]


def probe_data360():
    s = search_summary
    url = f"{DATA360}/searchv2"
    probe.get("T00", "official OpenAPI specification", OPENAPI, None, False,
              lambda d: {"info_version": d["info"]["version"], "paths": sorted(d["paths"])})
    post("T01", "count by type", url, {"count": True, "search": "*", "facets": ["type"], "top": 1}, False, s)
    base = {"count": True, "search": "finance", "filter": "type eq 'dataset'"}
    _, a = post("T02", "datasets, page 1 of 5", url, {**base, "top": 5, "skip": 0}, False, s)
    _, b = post("T03", "datasets, page 2 of 5", url, {**base, "top": 5, "skip": 5}, False, s)
    _, c = post("T04", "repeat of T02", url, {**base, "top": 5, "skip": 0}, False, s)
    _, d = post("T05", "datasets, page of 100", url, {**base, "top": 100, "skip": 0}, True, s)
    _, e = post("T06", "datasets, second page of 100", url, {**base, "top": 100, "skip": 100}, False, s)
    every = {"count": True, "search": "*", "filter": "type eq 'dataset'"}
    _, f = post("T07", "all datasets, first 100", url, {**every, "top": 100, "skip": 0}, True, s)
    _, g = post("T08", "all datasets, second 100", url, {**every, "top": 100, "skip": 100}, False, s)
    total = (f or {}).get("@odata.count") or 0
    post("T09", "skip beyond the total", url, {**every, "top": 5, "skip": total + 5}, False, s)
    nothing = {"count": True, "search": "zzqxnoresultsfdh"}
    post("T10", "no results", url, {**nothing, "top": 5}, False, s)
    post("T11", "large top on empty query", url, {**nothing, "top": 100000}, False, s)
    post("T12", "skip above 100000", url, {**nothing, "top": 5, "skip": 100001}, False, s)
    post("T13", "invalid top: negative", url, {**nothing, "top": -1}, False, s)
    post("T14", "invalid top: text", url, {**nothing, "top": "abc"}, False, s)
    post("T15", "invalid filter field", url, {**nothing, "filter": "not_a_field eq 'x'"}, False, s)
    post("T16", "unknown body property", url, {**nothing, "not_a_property": 1}, False, s)
    post("T17", "malformed JSON", url, "{", False, s)
    first = ids(f)[:1]
    if first:
        record, _ = post("T18", "metadata of one dataset", f"{DATA360}/metadata",
                         {"query": f"&$filter=series_description/idno eq '{first[0]}'"}, True)
    probe.get("T19", "indicators of one database", f"{DATA360}/indicators", {"datasetId": "WB_WDI"}, False,
              lambda d: {"type": type(d).__name__, "length": len(d)})
    for n in (1, 2, 3):
        post(f"L5.{n}", "latency repeat, 100 datasets", url, {**every, "top": 100})

    # Data Catalog retest: one request, at most two retries honouring Retry-After.
    for attempt in (1, 2, 3):
        record, data = probe.get(f"C01.{attempt}", "Data Catalog retest", f"{probe.CATALOG}/Search",
                                 {"qname": "dataset", "qterm": "finance", "$top": 1}, False, probe.catalog_summary)
        wait = int(record["retry_after"] or 60) + 1
        if record["status"] != 429 or attempt == 3 or wait > 61:
            break
        print(f"       waiting {wait} s (Retry-After)")
        time.sleep(wait)
    return {
        "page5_overlap": len(set(ids(a)) & set(ids(b))),
        "page5_repeat_same_order": ids(a) == ids(c),
        "finance_two_pages": {"returned": len(ids(d)) + len(ids(e)), "unique": len(set(ids(d)) | set(ids(e)))},
        "all_two_pages": {"returned": len(ids(f)) + len(ids(g)), "unique": len(set(ids(f)) | set(ids(g))),
                          "count": total},
    }


def probe_socrata():
    s = probe.socrata_summary
    base = {"domains": probe.DOMAIN, "only": "datasets", "q": "presupuesto"}
    _, a = probe.get("S30", "baseline, 100 results", probe.SOCRATA, {**base, "limit": 100}, False, s)
    _, b = probe.get("S31", "cursor paging, empty scroll_id", probe.SOCRATA,
                     {**base, "limit": 100, "scroll_id": ""}, False, s)
    seen = probe.socrata_ids(b)
    pages = [seen]
    for number in (2, 3):
        if not pages[-1]:
            break
        _, data = probe.get(f"S3{number}", f"cursor paging, page {number}", probe.SOCRATA,
                            {**base, "limit": 100, "scroll_id": pages[-1][-1]}, False, s)
        record = probe.records[-1]
        record["url"] = record["url"].replace(pages[-1][-1], "<last-id>")
        pages.append(probe.socrata_ids(data))
    probe.get("S34", "cursor combined with order", probe.SOCRATA,
              {**base, "limit": 5, "scroll_id": "", "order": "name"}, False, s)
    probe.get("S35", "limit above 100", probe.SOCRATA, {**base, "limit": 150}, False, s)
    every = [i for page in pages for i in page]
    return {
        "resultSetSize": (a or {}).get("resultSetSize"),
        "cursor_pages": [len(p) for p in pages],
        "cursor_returned": len(every),
        "cursor_unique": len(set(every)),
        "offset_and_cursor_first_page_same_ids": set(probe.socrata_ids(a)) == set(seen),
    }


TARGETS = {
    "socrata": (probe_socrata, "research/sources/colombia/socrata"),
    "data360": (probe_data360, "research/sources/international/world-bank"),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in TARGETS:
        sys.exit(f"usage: round2.py {{{'|'.join(TARGETS)}}}")
    run, folder = TARGETS[sys.argv[1]]
    started = probe.utc_now()
    head = subprocess.run(["git", "-C", str(probe.REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    checks = run()
    evidence = {
        "target": sys.argv[1],
        "started_utc": started,
        "finished_utc": probe.utc_now(),
        "repository_commit": head.stdout.strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256((HERE / "probe.py").read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "settings": {"timeout_s": probe.TIMEOUT_S, "delay_s": probe.DELAY_S, "authentication": "none"},
        "checks": checks,
        "requests": probe.records,
    }
    out = probe.REPO / folder / "evidence" / f"round2-{started.replace(':', '')}.json"
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks))
    print(out.relative_to(probe.REPO), f"({len(probe.records)} requests)")


if __name__ == "__main__":
    main()
