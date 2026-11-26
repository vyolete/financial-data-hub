"""Which Data360 fields could provide a dataset page URL and a publisher.

Usage (from the repository root):
    python3 -I research/experiments/discovery-probe/data360_links.py

Two read-only search requests cover every entry of type "dataset". Only aggregate
counts are stored: link types, host names, field names and whether a link embeds
the dataset identifier. No titles, identifiers, names or URLs are stored.
"""

import hashlib
import importlib.util
import json
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


def shape(value, identifier):
    """Describe a URL without storing it: scheme, host and whether it names the dataset."""
    parsed = urllib.parse.urlparse(str(value).strip())
    names = "with dataset id" if identifier and identifier in str(value) else "without dataset id"
    return f"{parsed.scheme or '-'}://{parsed.hostname or '<none>'} ({names})"


def analyse(items):
    link_types, link_shapes, url_fields = Counter(), Counter(), {}
    entity_keys = Counter()
    per_dataset = Counter()
    for item in items:
        identifier = item.get("idno")
        description = item.get("series_description") or {}
        links = [l for l in description.get("links") or [] if isinstance(l, dict)]
        per_dataset[len(links)] += 1
        for link in links:
            kind = str(link.get("type"))[:40]
            link_types[kind] += 1
            if probe.filled(link.get("uri")):
                link_shapes[f"{kind} | {shape(link['uri'], identifier)}"] += 1
        for field in ("api_explorer_link", "api_link", "json_link", "csv_link"):
            if probe.filled(description.get(field)):
                url_fields.setdefault(field, Counter())[shape(description[field], identifier)] += 1
        for field in ("sources", "authoring_entity"):
            for entry in description.get(field) or []:
                if isinstance(entry, dict):
                    entity_keys.update(f"{field}.{k}" for k, v in entry.items() if probe.filled(v))
    return {
        "datasets": len(items),
        "links_per_dataset": {str(k): v for k, v in sorted(per_dataset.items())},
        "link_types": dict(link_types.most_common(20)),
        "link_shapes": dict(link_shapes.most_common(40)),
        "url_fields": {k: dict(v.most_common(10)) for k, v in url_fields.items()},
        "entity_filled_keys": dict(entity_keys.most_common()),
    }


def main():
    started = probe.utc_now()
    items, total = [], None
    for page, skip in enumerate((0, PAGE), 1):
        _, data = post(f"K{page}", f"all datasets, page {page}", f"{round2.DATA360}/searchv2",
                       {"count": True, "search": "*", "filter": "type eq 'dataset'", "top": PAGE, "skip": skip})
        if not data or "value" not in data:
            sys.exit("stopping: unexpected response")
        items.extend(data["value"])
        total = data.get("@odata.count")
    checks = {"declared_total": total, "complete": total == len(items), **analyse(items)}
    head = subprocess.run(["git", "-C", str(probe.REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    evidence = {
        "target": "data360-links",
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
    out = folder / f"links-{started.replace(':', '')}.json"
    out.write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    print(out.relative_to(probe.REPO), f"({len(probe.records)} requests)")


if __name__ == "__main__":
    main()
