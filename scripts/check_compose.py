"""Check exposure and configuration access of the Compose project.

usage: docker compose config --format json | python3 scripts/check_compose.py
"""

import json
import sys

CONFIG_TARGET = "/app/config"
CONFIG_SERVICES = {"migrate", "api"}
LOOPBACK = "127.0.0.1"


def problems(project: dict) -> list[str]:
    found: list[str] = []
    services = project.get("services", {})
    missing = {"db", "migrate", "api", "web"} - set(services)
    if missing:
        found.append(f"missing services: {sorted(missing)}")
    for name, service in services.items():
        for port in service.get("ports", []):
            if port.get("host_ip") != LOOPBACK:
                found.append(f"{name}: port {port.get('published')} is not bound to {LOOPBACK}")
        if service.get("network_mode") == "host" or service.get("privileged"):
            found.append(f"{name}: host network or privileged mode")
        mounts = [v for v in service.get("volumes", []) if v.get("target") == CONFIG_TARGET]
        if name in CONFIG_SERVICES:
            if len(mounts) != 1 or not mounts[0].get("read_only"):
                found.append(f"{name}: the configuration must be mounted read-only")
        elif mounts or any(v.get("type") == "bind" for v in service.get("volumes", [])):
            found.append(f"{name}: must not mount host files")
        if name != "db" and not service.get("read_only"):
            found.append(f"{name}: the root filesystem must be read-only")
    return found


def main() -> int:
    found = problems(json.load(sys.stdin))
    for item in found:
        print(f"FAIL {item}")
    if not found:
        print("compose checks passed: loopback ports and read-only configuration")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
