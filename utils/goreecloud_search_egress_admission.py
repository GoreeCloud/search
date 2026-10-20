#!/usr/bin/env python3
"""Read-only Docker admission audit for GoreeCloud Search's shared Tor namespace.

Inspects only two fixed container identities and their assigned networks.
Does NOT check Internet DNS, firewall enforcement, Tor identity or provider IP.
Never prints raw inspection responses, environment settings, secrets or IPs.
"""
from __future__ import annotations

import json
import subprocess

SEARCH_NAME = "goreecloud-search"
TOR_NAME = "goreecloud-search-tor"


def assess(search: dict, tor: dict, networks: dict[str, dict]) -> list[str]:
    """Return bounded finding identifiers, never untrusted Docker field values."""
    findings: set[str] = set()
    if (search.get("Name") or "").lstrip("/") != SEARCH_NAME:
        findings.add("unexpected_search_container")
    if (tor.get("Name") or "").lstrip("/") != TOR_NAME:
        findings.add("unexpected_tor_container")

    search_host = search.get("HostConfig") or {}
    tor_host = tor.get("HostConfig") or {}
    tor_id = tor.get("Id")
    network_mode = search_host.get("NetworkMode")
    if not (isinstance(tor_id, str) and len(tor_id) >= 12
            and network_mode in ("container:" + tor_id, "container:" + tor_id[:12])):
        findings.add("search_tor_namespace_unverified")

    for prefix, container in (("search", search), ("tor", tor)):
        host = container.get("HostConfig") or {}
        cfg = container.get("Config") or {}
        if host.get("Privileged") is not False:
            findings.add(prefix + "_privileged")
        if host.get("ReadonlyRootfs") is not True:
            findings.add(prefix + "_writable_root")
        if str(cfg.get("User") or "").split(":")[0].lower() in ("", "0", "root"):
            findings.add(prefix + "_root_user")
        if "ALL" not in [str(c).upper() for c in (host.get("CapDrop") or [])]:
            findings.add(prefix + "_capabilities_enabled")
        if host.get("CapAdd"):
            findings.add(prefix + "_extra_capabilities")
        if "no-new-privileges" not in " ".join(
            str(x).lower() for x in (host.get("SecurityOpt") or [])
        ):
            findings.add(prefix + "_new_privileges_permitted")
        if host.get("PortBindings") or host.get("PublishAllPorts"):
            findings.add(prefix + "_host_ports_published")
        if host.get("PidMode") == "host" or host.get("IpcMode") == "host":
            findings.add(prefix + "_host_namespace")
    if tor_host.get("NetworkMode") == "host":
        findings.add("tor_host_network_mode")

    assigned = (tor.get("NetworkSettings") or {}).get("Networks") or {}
    if not assigned:
        findings.add("tor_networks_missing")
    if set(assigned) != set(networks):
        findings.add("network_inspection_incomplete")
    if any(networks.get(name, {}).get("Internal") is not True for name in assigned):
        findings.add("shared_namespace_has_external_route")
    if assigned and all(networks.get(name, {}).get("Internal") is True for name in assigned):
        findings.add("tor_outbound_route_unavailable")

    # Docker inspection cannot qualify routing/firewall/DNS/leak prevention.
    findings.add("host_firewall_and_live_leak_tests_unverified")
    return sorted(findings)


def _inspect(*args: str) -> dict:
    result = subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=12
    )
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise ValueError("invalid Docker inspection response")
    return parsed[0]


def main() -> int:
    try:
        search = _inspect("inspect", SEARCH_NAME)
        tor = _inspect("inspect", TOR_NAME)
        attached = (tor.get("NetworkSettings") or {}).get("Networks") or {}
        networks = {name: _inspect("network", "inspect", name) for name in attached}
        findings = assess(search, tor, networks)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        print("NOT_QUALIFIED: docker_inspection_unavailable")
        return 2
    print("NOT_QUALIFIED: " + ", ".join(findings))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
