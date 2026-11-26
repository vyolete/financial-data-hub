"""Bounded live probe of discovery APIs. Standard library only.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/probe.py socrata
    python3 -I research/experiments/discovery-probe/probe.py world-bank

Only sanitized evidence is written: status, timing, size, body hash, JSON schema
and aggregate counts. Record titles, descriptions, people names and identifiers
are never stored. No credentials are used and no request is retried.
"""

import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
USER_AGENT = "financial-data-hub-research/0.1 (+https://github.com/vyolete/financial-data-hub)"
TIMEOUT_S = 10
DELAY_S = 1.1  # www.datos.gov.co robots.txt declares Crawl-delay: 1
MAX_BYTES = 5_000_000
MAX_REQUESTS = 45

records = []


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrub(text):
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<email>", text)
    return re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "<ip>", text)


def schema(node, path="$", out=None):
    """Map each JSON path to the set of value types seen (keys only, never values)."""
    out = {} if out is None else out
    out.setdefault(path, set()).add(type(node).__name__)
    if len(path.split(".")) <= 5:
        if isinstance(node, dict):
            for key, value in node.items():
                schema(value, f"{path}.{key}", out)
        elif isinstance(node, list):
            for value in node:
                schema(value, f"{path}[]", out)
    return out


def get(probe_id, purpose, base, params=None, keep_schema=False, summarize=None):
    """Perform one GET, record sanitized evidence and return (record, parsed_json)."""
    if len(records) >= MAX_REQUESTS:
        raise RuntimeError("request budget exhausted")
    url = base + ("?" + urllib.parse.urlencode(params, safe="$") if params else "")
    record = {"id": probe_id, "purpose": purpose, "url": url, "utc": utc_now()}
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    body, headers = b"", {}
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            record["status"], headers = response.status, response.headers
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        record["status"], headers = error.code, error.headers
        body = error.read(MAX_BYTES + 1)
    except Exception as error:  # network failures are evidence, not crashes
        record["status"] = None
        record["transport_error"] = scrub(f"{type(error).__name__}: {error}")[:300]
    record["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    record["bytes"] = len(body)
    record["truncated"] = len(body) > MAX_BYTES
    record["content_type"] = headers.get("Content-Type") if headers else None
    record["retry_after"] = headers.get("Retry-After") if headers else None
    record["rate_limit_headers"] = {
        k: v for k, v in (headers.items() if headers else []) if "ratelimit" in k.lower().replace("-", "")
    }
    record["body_sha256"] = hashlib.sha256(body).hexdigest() if body else None
    data = None
    try:
        data = json.loads(body.decode("utf-8-sig"))
        record["json"] = True
    except (ValueError, UnicodeDecodeError):
        record["json"] = False
    if record["status"] and record["status"] >= 400:
        record["error_excerpt"] = scrub(body.decode("utf-8", "replace"))[:300]
    if data is not None:
        if keep_schema:
            record["schema"] = {k: sorted(v) for k, v in sorted(schema(data).items())}
        if summarize:
            try:
                record["summary"] = summarize(data)
            except Exception as error:
                record["summary_error"] = f"{type(error).__name__}: {error}"[:200]
    records.append(record)
    print(f"{probe_id:5} {record['status']} {record['elapsed_ms']:>6} ms {record['bytes']:>8} B  {purpose}")
    time.sleep(DELAY_S)
    return record, data


def filled(value):
    return value not in (None, "", [], {})


def short_values(items, getter, top=15):
    values = Counter()
    for item in items:
        value = getter(item)
        values[value[:100] if isinstance(value, str) else f"<{type(value).__name__}>"] += 1
    return dict(values.most_common(top))


# ---------------------------------------------------------------- Socrata

SOCRATA = "https://api.us.socrata.com/api/catalog/v1"
DOMAIN = "www.datos.gov.co"


def socrata_summary(data):
    if "results" not in data:
        return {"top_level_keys": sorted(data), "error": scrub(str(data.get("error", "")))[:300]}
    results = data["results"]
    ids = [r.get("resource", {}).get("id") for r in results]
    paths = [
        "resource.id", "resource.name", "resource.description", "resource.attribution",
        "resource.createdAt", "resource.updatedAt", "resource.data_updated_at",
        "resource.metadata_updated_at", "resource.publication_date",
        "classification.domain_category", "classification.domain_tags",
        "classification.categories", "classification.tags",
        "metadata.domain", "metadata.license", "permalink", "link",
    ]

    def dig(item, path):
        for key in path.split("."):
            item = item.get(key) if isinstance(item, dict) else None
        return item

    return {
        "top_level_keys": sorted(data),
        "resultSetSize": data.get("resultSetSize"),
        "returned": len(results),
        "unique_ids": len(set(ids)),
        "server_timings": data.get("timings"),
        "types": short_values(results, lambda r: dig(r, "resource.type")),
        "domains": short_values(results, lambda r: dig(r, "metadata.domain")),
        "filled_fields": {p: sum(filled(dig(r, p)) for r in results) for p in paths},
        "licenses": short_values(results, lambda r: dig(r, "metadata.license")),
        "domain_categories": short_values(results, lambda r: dig(r, "classification.domain_category")),
    }


def socrata_ids(data):
    return [r["resource"]["id"] for r in (data or {}).get("results", [])]


def probe_socrata():
    base = {"domains": DOMAIN, "only": "datasets"}
    term = {**base, "q": "presupuesto"}
    nothing = {**base, "q": "zzqxnoresultsfdh"}
    s = socrata_summary

    _, first = get("S01", "baseline, one dataset", SOCRATA, {**base, "limit": 1}, True, s)
    get("S02", "same request on the portal host", f"https://{DOMAIN}/api/catalog/v1", {**base, "limit": 1}, False, s)
    get("S03", "with search_context", SOCRATA, {**base, "search_context": DOMAIN, "limit": 1}, False, s)
    _, a = get("S04", "term, page 1 of 5", SOCRATA, {**term, "limit": 5, "offset": 0}, False, s)
    _, b = get("S05", "term, page 2 of 5", SOCRATA, {**term, "limit": 5, "offset": 5}, False, s)
    _, c = get("S06", "repeat of S04", SOCRATA, {**term, "limit": 5, "offset": 0}, False, s)
    _, d = get("S07", "term, page 1 of 100", SOCRATA, {**term, "limit": 100, "offset": 0}, True, s)
    _, e = get("S08", "term, page 2 of 100", SOCRATA, {**term, "limit": 100, "offset": 100}, False, s)
    checks = {
        "page5_overlap": len(set(socrata_ids(a)) & set(socrata_ids(b))),
        "page5_repeat_same_order": socrata_ids(a) == socrata_ids(c),
        "page100_overlap": len(set(socrata_ids(d)) & set(socrata_ids(e))),
    }
    total = (d or {}).get("resultSetSize") or 0
    get("S09", "offset beyond result set", SOCRATA, {**term, "limit": 5, "offset": total + 5}, False, s)
    get("S10", "term with no results", SOCRATA, {**nothing, "limit": 5}, False, s)
    get("S11", "offset + limit just under 10000", SOCRATA, {**base, "limit": 10, "offset": 9990}, False, s)
    get("S12", "offset + limit over 10000", SOCRATA, {**base, "limit": 10, "offset": 10000}, False, s)
    get("S13", "invalid limit: negative", SOCRATA, {**nothing, "limit": -1}, False, s)
    get("S14", "invalid limit: text", SOCRATA, {**nothing, "limit": "abc"}, False, s)
    get("S15", "limit above 10000 on empty query", SOCRATA, {**nothing, "limit": 10001}, False, s)
    get("S16", "invalid only value", SOCRATA, {"domains": DOMAIN, "only": "notatype", "limit": 1}, False, s)
    get("S17", "unknown domain", SOCRATA, {"domains": "unknown.invalid", "only": "datasets", "limit": 1}, False, s)
    get("S18", "term without only filter", SOCRATA, {"domains": DOMAIN, "q": "presupuesto", "limit": 100}, False, s)
    get("S19", "term with accent", SOCRATA, {**base, "q": "inversión", "limit": 1}, False, s)
    get("S20", "term without accent", SOCRATA, {**base, "q": "inversion", "limit": 1}, False, s)
    for n in (1, 2, 3):
        get(f"L1.{n}", "latency repeat, 1 result", SOCRATA, {**base, "limit": 1})
        get(f"L2.{n}", "latency repeat, 100 results", SOCRATA, {**term, "limit": 100})

    ids = socrata_ids(first)
    if ids:
        def view_summary(data):
            return {
                "has_licenseId": filled(data.get("licenseId")),
                "licenseId": data.get("licenseId"),
                "license_keys": sorted(data.get("license") or {}),
                "license_name": (data.get("license") or {}).get("name"),
                "has_attribution": filled(data.get("attribution")),
                "assetType": data.get("assetType"),
            }

        view = f"https://{DOMAIN}/api/views/{ids[0]}.json"
        record, _ = get("S21", "single asset metadata (first S01 result)", view, None, True, view_summary)
        record["url"] = record["url"].replace(ids[0], "<dataset-id>")
    return checks


# ---------------------------------------------------------------- World Bank

INDICATORS = "https://api.worldbank.org/v2"
CATALOG = "https://datacatalogapi.worldbank.org/ddhxext"


def indicators_summary(data):
    if not (isinstance(data, list) and len(data) == 2 and isinstance(data[1], (list, type(None)))):
        return {"shape": type(data).__name__, "body_excerpt": scrub(json.dumps(data))[:400]}
    meta, items = data[0], data[1] or []
    keys = sorted({k for i in items for k in i})
    return {
        "meta": meta,
        "returned": len(items),
        "unique_ids": len({i.get("id") for i in items}),
        "filled_fields": {k: sum(filled(i.get(k)) for i in items) for k in keys},
    }


def item_list(data):
    """Return the first list of objects found at the top level."""
    if isinstance(data, list):
        return data, None
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value, key
    return [], None


def catalog_summary(data):
    items, key = item_list(data)
    keys = sorted({k for i in items for k in i})
    scalars = {k: v for k, v in data.items() if isinstance(v, (int, bool))} if isinstance(data, dict) else {}
    out = {
        "top_level_keys": sorted(data) if isinstance(data, dict) else "<list>",
        "numeric_top_level": scalars,
        "list_key": key,
        "returned": len(items),
        "filled_fields": {k: sum(filled(i.get(k)) for i in items) for k in keys},
        "license_like_values": {
            k: short_values(items, lambda i, k=k: i.get(k))
            for k in keys if re.search(r"licen|classification|data_type|dataset_type", k, re.I)
        },
    }
    if not items:
        out["body_excerpt"] = scrub(json.dumps(data))[:300]
    return out


def item_keys(data):
    items = item_list(data)[0] if data else []
    return [i.get("dataset_unique_id") or i.get("dataset_id") or json.dumps(i, sort_keys=True) for i in items]


def probe_world_bank():
    i, c = indicators_summary, catalog_summary
    fmt = {"format": "json"}
    get("W01", "sources", f"{INDICATORS}/sources", {**fmt, "per_page": 100}, True, i)
    _, a = get("W02", "indicators, page 1 of 5", f"{INDICATORS}/indicator", {**fmt, "per_page": 5, "page": 1}, True, i)
    _, b = get("W03", "indicators, page 2 of 5", f"{INDICATORS}/indicator", {**fmt, "per_page": 5, "page": 2}, False, i)
    get("W04", "indicators, page of 100", f"{INDICATORS}/indicator", {**fmt, "per_page": 100}, False, i)
    pages = a[0].get("pages", 0) if isinstance(a, list) and a else 0
    get("W05", "page beyond the last", f"{INDICATORS}/indicator", {**fmt, "per_page": 5, "page": int(pages) + 1}, False, i)
    get("W06", "unknown indicator", f"{INDICATORS}/indicator/NOT.A.REAL.CODE", fmt, False, i)
    get("W07", "invalid per_page: text", f"{INDICATORS}/indicator", {**fmt, "per_page": "abc"}, False, i)
    get("W08", "invalid per_page: zero", f"{INDICATORS}/indicator", {**fmt, "per_page": 0}, False, i)
    get("W09", "indicators of source 2", f"{INDICATORS}/source/2/indicator", {**fmt, "per_page": 5}, False, i)
    get("W10", "default format", f"{INDICATORS}/indicator", {"per_page": 1})
    get("W11", "exploratory text search parameter", f"{INDICATORS}/indicator", {**fmt, "per_page": 1, "q": "gdp"}, False, i)

    _, d1 = get("D01", "dataset list, page 1 of 5", f"{CATALOG}/DatasetList", {"$top": 5, "$skip": 0}, True, c)
    _, d2 = get("D02", "dataset list, page 2 of 5", f"{CATALOG}/DatasetList", {"$top": 5, "$skip": 5}, False, c)
    get("D03", "dataset list, page of 100", f"{CATALOG}/DatasetList", {"$top": 100, "$skip": 0}, False, c)
    search = {"qname": "dataset", "qterm": "finance"}
    _, s1 = get("D04", "search, page 1 of 5", f"{CATALOG}/Search", {**search, "$top": 5, "$skip": 0}, True, c)
    _, s2 = get("D05", "search, page 2 of 5", f"{CATALOG}/Search", {**search, "$top": 5, "$skip": 5}, False, c)
    _, s3 = get("D06", "repeat of D04", f"{CATALOG}/Search", {**search, "$top": 5, "$skip": 0}, False, c)
    get("D07", "search, page of 100", f"{CATALOG}/Search", {**search, "$top": 100}, False, c)
    get("D08", "search with no results", f"{CATALOG}/Search", {"qname": "dataset", "qterm": "zzqxnoresultsfdh", "$top": 5}, False, c)
    get("D09", "search without qname", f"{CATALOG}/Search", {"qterm": "finance", "$top": 1}, False, c)
    get("D10", "invalid top: negative", f"{CATALOG}/DatasetList", {"$top": -1}, False, c)
    get("D11", "skip beyond the end", f"{CATALOG}/DatasetList", {"$top": 5, "$skip": 10000000}, False, c)

    first = (item_list(s1)[0] or item_list(d1)[0]) if (s1 or d1) else []
    unique_id = first[0].get("dataset_unique_id") if first else None
    if unique_id:
        record, _ = get("D12", "dataset detail (first search result)", f"{CATALOG}/DatasetView",
                        {"dataset_unique_id": unique_id}, True)
        record["url"] = record["url"].replace(str(unique_id), "<dataset-id>")
    get("D13", "unknown dataset detail", f"{CATALOG}/DatasetView", {"dataset_unique_id": "0000000"}, False)
    for n in (1, 2, 3):
        get(f"L3.{n}", "latency repeat, indicators", f"{INDICATORS}/indicator", {**fmt, "per_page": 100})
        get(f"L4.{n}", "latency repeat, catalog search", f"{CATALOG}/Search", {**search, "$top": 100})
    return {
        "indicators_page_overlap": len(
            {x["id"] for x in (a or [{}, []])[1]} & {x["id"] for x in (b or [{}, []])[1]}),
        "catalog_list_overlap": len(set(item_keys(d1)) & set(item_keys(d2))),
        "catalog_search_overlap": len(set(item_keys(s1)) & set(item_keys(s2))),
        "catalog_search_repeat_same_order": item_keys(s1) == item_keys(s3),
    }


TARGETS = {
    "socrata": (probe_socrata, "research/sources/colombia/socrata"),
    "world-bank": (probe_world_bank, "research/sources/international/world-bank"),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in TARGETS:
        sys.exit(f"usage: probe.py {{{'|'.join(TARGETS)}}}")
    probe, folder = TARGETS[sys.argv[1]]
    started = utc_now()
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    checks = probe()
    evidence = {
        "target": sys.argv[1],
        "started_utc": started,
        "finished_utc": utc_now(),
        "repository_commit": head.stdout.strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "settings": {"timeout_s": TIMEOUT_S, "delay_s": DELAY_S, "retries": 0, "authentication": "none"},
        "checks": checks,
        "requests": records,
    }
    out = REPO / folder / "evidence" / f"probe-{started.replace(':', '')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks))
    print(out.relative_to(REPO), f"({len(records)} requests)")


if __name__ == "__main__":
    main()
