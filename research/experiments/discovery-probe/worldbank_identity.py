"""World Bank Indicators API: identifier uniqueness across statistical sources.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/worldbank_identity.py

Also measures topic multiplicity, checks the topic filter and samples the
metadata API for per-indicator license fields. Reuses the sanitized recorder of
probe.py: indicator codes, names and descriptions are never stored, only counts,
numeric source ids, field names, license labels and hashes of identifier sets.
HTTP 429 and 5xx or transport failures are retried at most three times; a
Retry-After above 60 s stops the run.
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probe", HERE / "probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

probe.USER_AGENT = "generic-research-probe/0.1"
probe.TIMEOUT_S = 60  # large research pages; not the product timeout
probe.MAX_BYTES = 60_000_000
probe.MAX_REQUESTS = 260

API = probe.INDICATORS
JSON_FORMAT = {"format": "json"}
PAGE_SIZE = 5000
MAX_PAGES = 10
MAX_RETRIES = 3
MAX_WAIT_S = 60


def fetch(probe_id, purpose, url, params):
    for attempt in range(MAX_RETRIES + 1):
        record, data = probe.get(f"{probe_id}.{attempt + 1}", purpose, url, params)
        status = record["status"]
        if status is not None and status != 429 and status < 500:
            return record, data
        wait = record["retry_after"]
        wait = int(wait) if wait and wait.isdigit() else 2 ** (attempt + 1)
        if wait > MAX_WAIT_S:
            sys.exit(f"stopping: Retry-After {wait} s exceeds {MAX_WAIT_S} s")
        if attempt < MAX_RETRIES:
            time.sleep(wait)
    return record, data


def shape(data):
    """Return (meta, items) or (None, None) for anything else, including 200 errors."""
    if isinstance(data, list) and len(data) == 2 and isinstance(data[1], (list, type(None))):
        return data[0], data[1] or []
    return None, None


def paged(prefix, purpose, url):
    """Fetch every page of a collection; return (items, complete, declared_total)."""
    items, total = [], None
    for page in range(1, MAX_PAGES + 1):
        _, data = fetch(f"{prefix}.p{page}", f"{purpose}, page {page}", url,
                        {**JSON_FORMAT, "per_page": PAGE_SIZE, "page": page})
        meta, chunk = shape(data)
        if meta is None:
            return items, False, total
        total = int(meta.get("total", 0))
        items.extend(chunk)
        if page >= int(meta.get("pages", 0)):
            return items, len(items) == total, total
    return items, False, total


def digest(values):
    return hashlib.sha256("\n".join(sorted(values)).encode()).hexdigest()


def spread(values, size):
    """Deterministic, evenly spaced sample of a sorted list."""
    values = sorted(values)
    if len(values) <= size:
        return values
    return [values[i * len(values) // size] for i in range(size)]


def run():
    sources, sources_complete, _ = paged("A", "sources", f"{API}/sources")
    source_ids = sorted((str(s["id"]) for s in sources), key=int)

    everything, global_complete, global_total = paged("B", "all indicators", f"{API}/indicator")
    global_ids = [i["id"] for i in everything]

    by_source, per_source, mismatched = {}, {}, 0
    for source_id in source_ids:
        items, complete, total = paged(f"C{source_id}", f"indicators of source {source_id}",
                                       f"{API}/source/{source_id}/indicator")
        ids = [i["id"] for i in items]
        by_source[source_id] = {i["id"]: i for i in items}
        per_source[source_id] = {
            "declared_total": total,
            "returned": len(ids),
            "distinct": len(set(ids)),
            "complete": complete,
        }
        mismatched += sum(str((i.get("source") or {}).get("id")) != source_id for i in items)

    owners = defaultdict(list)
    for source_id, items in by_source.items():
        for indicator_id in items:
            owners[indicator_id].append(source_id)
    shared = {k: v for k, v in owners.items() if len(v) > 1}
    pairs = Counter()
    for found_in in shared.values():
        ordered = sorted(found_in, key=int)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                pairs[f"{left}+{right}"] += 1
    differing_names = sum(
        len({(by_source[s][k].get("name") or "").strip() for s in v}) > 1 for k, v in shared.items())
    lowered = Counter(k.lower() for k in owners)
    union = set(owners)
    topics = Counter(len([t for t in (i.get("topics") or []) if t.get("id")]) for i in everything)

    topic_items, _, _ = paged("D", "topics", f"{API}/topic")
    topic_check = {}
    _, data = fetch("E", "indicators of topic 7", f"{API}/topic/7/indicator", {**JSON_FORMAT, "per_page": 100})
    meta, chunk = shape(data)
    if meta is not None:
        topic_check = {
            "total": meta.get("total"),
            "returned": len(chunk),
            "returned_without_topic_7": sum(
                "7" not in {str(t.get("id")) for t in (i.get("topics") or [])} for i in chunk),
            "distinct_sources": sorted({str((i.get("source") or {}).get("id")) for i in chunk}),
        }

    # Metadata API sample: one indicator per source plus 25 spread over source 2 (WDI).
    targets = [(s, spread(by_source[s], 3)[-1]) for s in source_ids if by_source[s]]
    targets += [("2", i) for i in spread(by_source.get("2", {}), 25)]
    fields, licenses, outcomes = Counter(), Counter(), Counter()
    license_by_source = defaultdict(set)
    for number, (source_id, indicator_id) in enumerate(targets, 1):
        url = f"{API}/sources/{source_id}/series/{urllib.parse.quote(indicator_id, safe='')}/metadata"
        record, data = fetch(f"M{number}", f"metadata of one indicator, source {source_id}", url, JSON_FORMAT)
        record["url"] = record["url"].replace(urllib.parse.quote(indicator_id, safe=""), "<indicator-id>")
        record.pop("error_excerpt", None)
        found = {}
        try:
            for src in data["source"]:
                for concept in src["concept"]:
                    for variable in concept["variable"]:
                        for item in variable["metatype"]:
                            found[item["id"]] = item.get("value")
        except (KeyError, TypeError):
            pass
        outcomes["with_metadata" if found else "without_metadata"] += 1
        fields.update(k for k, v in found.items() if probe.filled(v))
        if found:
            label = next((v for k, v in found.items() if re.fullmatch(r"license_?type", k, re.I)), None)
            label = probe.scrub(str(label).strip())[:100] if label else "<absent>"
            licenses[label] += 1
            license_by_source[label].add(source_id)

    return {
        "sources": {"count": len(source_ids), "complete": sources_complete},
        "global_list": {
            "declared_total": global_total, "returned": len(global_ids),
            "distinct": len(set(global_ids)), "complete": global_complete,
            "sha256_distinct_ids": digest(set(global_ids)),
        },
        "per_source": per_source,
        "per_source_summary": {
            "sources_with_indicators": sum(bool(v) for v in by_source.values()),
            "sources_incomplete": [s for s, v in per_source.items() if not v["complete"]],
            "sources_with_internal_duplicates": [
                s for s, v in per_source.items() if v["returned"] != v["distinct"]],
            "sum_distinct_per_source": sum(len(v) for v in by_source.values()),
            "distinct_across_sources": len(union),
            "items_whose_source_differs_from_request": mismatched,
        },
        "cross_source": {
            "ids_in_more_than_one_source": len(shared),
            "max_sources_for_one_id": max((len(v) for v in shared.values()), default=1),
            "shared_ids_with_different_names": differing_names,
            "source_pairs": dict(pairs.most_common()),
            "sha256_shared_ids": digest(shared),
            "case_insensitive_collisions": sum(n > 1 for n in lowered.values()),
            "only_in_global_list": len(set(global_ids) - union),
            "only_in_source_lists": len(union - set(global_ids)),
        },
        "identifier_format": {
            "max_length": max(map(len, union), default=0),
            "with_surrounding_whitespace": sum(k != k.strip() for k in union),
            "non_alphanumeric_characters": sorted({c for k in union for c in k if not c.isalnum()}),
        },
        "topics": {
            "defined": len(topic_items),
            "indicators_by_topic_count": {str(k): v for k, v in sorted(topics.items())},
            "topic_filter": topic_check,
        },
        "metadata_sample": {
            "requested": len(targets), "outcomes": dict(outcomes),
            "filled_fields": dict(fields.most_common()),
            "license_labels": dict(licenses.most_common()),
            "license_label_sources": {k: sorted(v, key=int) for k, v in license_by_source.items()},
        },
    }


def main():
    started = probe.utc_now()
    head = subprocess.run(["git", "-C", str(probe.REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    checks = run()
    evidence = {
        "target": "world-bank-identity",
        "started_utc": started,
        "finished_utc": probe.utc_now(),
        "repository_commit": head.stdout.strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256((HERE / "probe.py").read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "settings": {"timeout_s": probe.TIMEOUT_S, "delay_s": probe.DELAY_S, "page_size": PAGE_SIZE,
                     "max_retries": MAX_RETRIES, "authentication": "none"},
        "checks": checks,
        "requests": probe.records,
    }
    folder = probe.REPO / "research/sources/international/world-bank/evidence"
    out = folder / f"identity-{started.replace(':', '')}.json"
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in checks.items() if k != "per_source"}, indent=1, ensure_ascii=False))
    print(out.relative_to(probe.REPO), f"({len(probe.records)} requests)")


if __name__ == "__main__":
    main()
