"""Review how Data360 datasets declare their licences, including external and absent ones.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/data360_licenses.py

Two read-only search requests cover every entry of type "dataset". Only aggregate
counts are stored: licence names, link host names and identifier prefixes (the
text before the first underscore). No titles, identifiers or notes are stored.
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("round2", HERE / "round2.py")
round2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round2)
probe, post = round2.probe, round2.post

PAGE = 100


def group_of(entries):
    names = [str(e.get("name") or "").strip() for e in entries]
    if not any(names):
        return "absent"
    if any(re.search(r"external", n, re.I) for n in names):
        return "external"
    if any(re.search(r"\b(NC|ND)\b", n) for n in names):
        return "non_commercial_or_no_derivatives"
    if all(re.match(r"CC[ -]?BY([ -]?4\.0)?$", n, re.I) for n in names):
        return "cc_by_4_or_unversioned"
    return "other_named"


def host_of(uri):
    return urllib.parse.urlparse(str(uri).strip()).hostname or "<not a URL>"


def analyse(items):
    names, per_dataset = Counter(), Counter()
    groups = {}
    for item in items:
        description = item.get("series_description") or {}
        entries = [e for e in description.get("license") or [] if isinstance(e, dict)]
        per_dataset[len(entries)] += 1
        names.update(str(e.get("name") or "<unnamed>").strip()[:100] for e in entries)
        group = groups.setdefault(group_of(entries), {
            "datasets": 0, "with_licence_link": 0, "with_licence_note": 0,
            "with_citation_requirement": 0, "link_hosts": Counter(), "identifier_prefixes": Counter()})
        group["datasets"] += 1
        links = [e["uri"] for e in entries if probe.filled(e.get("uri"))]
        group["with_licence_link"] += bool(links)
        group["with_licence_note"] += any(probe.filled(e.get("note")) for e in entries)
        group["with_citation_requirement"] += probe.filled(description.get("citation_requirement"))
        group["link_hosts"].update({host_of(u) for u in links})
        prefix = str(item.get("idno") or "").split("_")[0]
        group["identifier_prefixes"][prefix if re.fullmatch(r"[A-Za-z0-9]{1,12}", prefix) else "<other>"] += 1
    for group in groups.values():
        group["link_hosts"] = dict(group["link_hosts"].most_common())
        group["identifier_prefixes"] = dict(group["identifier_prefixes"].most_common())
    return {
        "datasets": len(items),
        "distinct_identifiers": len({i.get("idno") for i in items}),
        "licence_entries_per_dataset": {str(k): v for k, v in sorted(per_dataset.items())},
        "licence_names": dict(names.most_common()),
        "groups": groups,
    }


def main():
    started = probe.utc_now()
    items, total = [], None
    for page, skip in enumerate((0, PAGE), 1):
        _, data = post(f"G{page}", f"all datasets, page {page}", f"{round2.DATA360}/searchv2",
                       {"count": True, "search": "*", "filter": "type eq 'dataset'", "top": PAGE, "skip": skip})
        if not data or "value" not in data:
            sys.exit("stopping: unexpected response")
        items.extend(data["value"])
        total = data.get("@odata.count")
    checks = {"declared_total": total, "complete": total == len(items), **analyse(items)}
    head = subprocess.run(["git", "-C", str(probe.REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    evidence = {
        "target": "data360-licences",
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
    folder = probe.REPO / "research/sources/international/world-bank/evidence"
    out = folder / f"licences-{started.replace(':', '')}.json"
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    print(out.relative_to(probe.REPO), f"({len(probe.records)} requests)")


if __name__ == "__main__":
    main()
