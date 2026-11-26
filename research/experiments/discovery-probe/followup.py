"""Follow-up checks after probe.py: Socrata page stability and World Bank throttling.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/followup.py

Reuses the sanitized request recorder of probe.py. HTTP 429 is retried at most
three times, waiting for Retry-After. The catalog check stops as soon as one
request exhausts its retries.
"""

import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probe", HERE / "probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

MAX_RETRIES = 3
MAX_WAIT_S = 60


def save(target, folder, started, checks):
    head = subprocess.run(["git", "-C", str(probe.REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    evidence = {
        "target": target,
        "started_utc": started,
        "finished_utc": probe.utc_now(),
        "repository_commit": head.stdout.strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256((HERE / "probe.py").read_bytes()).hexdigest(),
        "checks": checks,
        "requests": probe.records,
    }
    out = probe.REPO / folder / "evidence" / f"followup-{started.replace(':', '')}.json"
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks))
    print(out.relative_to(probe.REPO), f"({len(probe.records)} requests)")
    probe.records.clear()


def socrata_page_stability():
    started = probe.utc_now()
    checks = {}
    for label, order in (("default", None), ("createdAt", "createdAt"), ("name", "name")):
        pages = []
        total = None
        for offset in (0, 100):
            params = {"domains": probe.DOMAIN, "only": "datasets", "q": "presupuesto", "limit": 100, "offset": offset}
            if order:
                params["order"] = order
            record, data = probe.get(f"F-{label}-{offset}", f"order={label}, offset={offset}", probe.SOCRATA, params)
            pages.append(probe.socrata_ids(data))
            total = (data or {}).get("resultSetSize", total)
        checks[label] = {
            "resultSetSize": total,
            "returned": sum(map(len, pages)),
            "unique": len(set(pages[0]) | set(pages[1])),
            "overlap": len(set(pages[0]) & set(pages[1])),
        }
    save("socrata-page-stability", "research/sources/colombia/socrata", started, checks)


def get_with_retry(probe_id, purpose, url, params):
    for attempt in range(1, MAX_RETRIES + 2):
        record, data = probe.get(f"{probe_id}.{attempt}", purpose, url, params, True, probe.catalog_summary)
        if record["status"] != 429:
            return record, data
        wait = int(record["retry_after"] or MAX_WAIT_S) + 1
        if attempt > MAX_RETRIES or wait > MAX_WAIT_S + 1:
            break
        print(f"      waiting {wait} s (Retry-After)")
        time.sleep(wait)
    return record, None


def world_bank_catalog():
    started = probe.utc_now()
    search = {"qname": "dataset", "qterm": "finance", "$top": 5}
    plan = [
        ("R01", "search, page 1", f"{probe.CATALOG}/Search", {**search, "$skip": 0}),
        ("R02", "dataset list, page 1", f"{probe.CATALOG}/DatasetList", {"$top": 5, "$skip": 0}),
        ("R03", "search, page 2", f"{probe.CATALOG}/Search", {**search, "$skip": 5}),
    ]
    results = {}
    for probe_id, purpose, url, params in plan:
        record, data = get_with_retry(probe_id, purpose, url, params)
        results[probe_id] = data
        if data is None:
            break
    first = probe.item_list(results["R01"])[0] if results.get("R01") else []
    unique_id = first[0].get("dataset_unique_id") if first else None
    if unique_id and results.get("R03") is not None:
        record, _ = get_with_retry("R04", "dataset detail", f"{probe.CATALOG}/DatasetView",
                                   {"dataset_unique_id": unique_id})
        record["url"] = record["url"].replace(str(unique_id), "<dataset-id>")
        record.pop("summary", None)
    for record in probe.records:
        record["url"] = record["url"].replace(str(unique_id), "<dataset-id>") if unique_id else record["url"]
    checks = {
        "succeeded": [k for k, v in results.items() if v is not None],
        "attempts": len(probe.records),
        "statuses": [r["status"] for r in probe.records],
    }
    save("world-bank-catalog-throttling", "research/sources/international/world-bank", started, checks)


if __name__ == "__main__":
    socrata_page_stability()
    world_bank_catalog()
