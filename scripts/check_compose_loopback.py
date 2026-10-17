"""Require published Compose ports to bind only to the local machine."""

import json
import sys

LOOPBACK_ADDRESS = "127.0.0.1"


def main() -> None:
    try:
        config = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise SystemExit(f"Could not parse resolved Compose configuration: {error}") from error

    services = config.get("services")
    if not isinstance(services, dict) or not services:
        raise SystemExit("Resolved Compose configuration contains no services")

    published_ports = 0
    violations: list[str] = []

    for service_name, service in services.items():
        if not isinstance(service, dict):
            violations.append(f"{service_name}: invalid service configuration")
            continue

        ports = service.get("ports", [])
        if not isinstance(ports, list):
            violations.append(f"{service_name}: invalid port configuration")
            continue

        for port in ports:
            if not isinstance(port, dict):
                violations.append(f"{service_name}: invalid published port mapping")
                continue
            if port.get("published") is None:
                continue

            published_ports += 1
            host_ip = port.get("host_ip")
            if host_ip != LOOPBACK_ADDRESS:
                violations.append(
                    f"{service_name}: published port {port['published']} binds to "
                    f"{host_ip or 'all interfaces'}, expected {LOOPBACK_ADDRESS}"
                )

    if published_ports == 0:
        raise SystemExit("Resolved Compose configuration contains no published ports")
    if violations:
        raise SystemExit("\n".join(violations))

    print(f"All {published_ports} published Compose ports bind to {LOOPBACK_ADDRESS}.")


if __name__ == "__main__":
    main()
