"""Data360 dataset checks. Corrects round2.py, which read the wrong identifier field.

In search results of type "dataset" the identifier is the top-level "idno", not
"series_description.idno" as in the indicator examples of the specification.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/round2_datasets.py
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("round2", HERE / "round2.py")
round2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round2)
probe, post = round2.probe, round2.post


def ids(data):
    return [item.get("idno") for item in (data or {}).get("value", [])]


def rights_summary(data):
    items = data.get("value", [])
    descriptions = [item.get("series_description") or {} for item in items]
    licenses = Counter()
    license_keys = Counter()
    for description in descriptions:
        entries = description.get("license") or []
        if not entries:
            licenses["<none>"] += 1
        for entry in entries:
            license_keys.update(k for k, v in entry.items() if probe.filled(v))
            licenses[str(entry.get("name") or entry.get("type") or "<unnamed>")[:100]] += 1
    return {
        "returned": len(items),
        "unique_idno": len(set(ids(data))),
        "licenses": dict(licenses.most_common(15)),
        "license_entry_keys": dict(license_keys),
        "confidentiality": probe.short_values(items, lambda i: i.get("data_confidentiality_name")),
        "with_citation_requirement": sum(probe.filled(d.get("citation_requirement")) for d in descriptions),
        "idno_equals_database_id": sum(i.get("idno") == d.get("database_id") for i, d in zip(items, descriptions)),
    }


def main():
    started = probe.utc_now()
    url = f"{round2.DATA360}/searchv2"
    every = {"count": True, "search": "*", "filter": "type eq 'dataset'"}
    finance = {"count": True, "search": "finance", "filter": "type eq 'dataset'"}
    _, a = post("U01", "all datasets, first 100", url, {**every, "top": 100, "skip": 0}, False, rights_summary)
    _, b = post("U02", "all datasets, second 100", url, {**every, "top": 100, "skip": 100}, False, rights_summary)
    _, c = post("U03", "finance, page 1 of 20", url, {**finance, "top": 20, "skip": 0})
    _, d = post("U04", "finance, page 2 of 20", url, {**finance, "top": 20, "skip": 20})
    _, e = post("U05", "finance, page 3 of 20", url, {**finance, "top": 20, "skip": 40})
    _, f = post("U06", "repeat of U03", url, {**finance, "top": 20, "skip": 0})
    first = ids(a)[:1]
    if first:
        record, _ = post("U07", "one dataset by identifier", url,
                         {"count": True, "search": "*", "filter": f"type eq 'dataset' and idno eq '{first[0]}'",
                          "top": 2}, False, lambda data: {"count": data.get("@odata.count")})
        record["request_body"]["filter"] = "type eq 'dataset' and idno eq '<dataset-id>'"
    every_ids = ids(a) + ids(b)
    finance_ids = ids(c) + ids(d) + ids(e)
    checks = {
        "all": {"count": (a or {}).get("@odata.count"), "returned": len(every_ids), "unique": len(set(every_ids))},
        "finance": {"count": (c or {}).get("@odata.count"), "returned": len(finance_ids),
                    "unique": len(set(finance_ids))},
        "finance_repeat_same_order": ids(c) == ids(f),
    }
    head = subprocess.run(["git", "-C", str(probe.REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    evidence = {
        "target": "data360-datasets",
        "started_utc": started,
        "finished_utc": probe.utc_now(),
        "repository_commit": head.stdout.strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "round2_sha256": hashlib.sha256((HERE / "round2.py").read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256((HERE / "probe.py").read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "checks": checks,
        "requests": probe.records,
    }
    out = probe.REPO / "research/sources/international/world-bank/evidence" / f"round2-datasets-{started.replace(':', '')}.json"
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks))
    print(out.relative_to(probe.REPO), f"({len(probe.records)} requests)")


if __name__ == "__main__":
    main()
