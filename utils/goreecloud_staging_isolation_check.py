#!/usr/bin/env python3
"""Read-only Docker isolation preflight for a *future* Search staging container.

DOES NOT attest egress firewall, DNS rebinding, visitor IP masking or
provider availability. Refuses to inspect arbitrary production containers.
Prints neither Docker environment variables nor secret-bearing metadata.
"""
import argparse
import json
import subprocess

STAGING_CONTAINER = "goreecloud-search-private-staging"
STAGING_NETWORK = "goreecloud-search-staging-egress"


def evaluate(container: dict, network: dict) -> list[str]:
    """Return invariant identifiers for unsafe staging configuration."""
    errors = []
    host = container.get("HostConfig") or {}
    cfg = container.get("Config") or {}
    net = container.get("NetworkSettings") or {}
    docker_networks = net.get("Networks") or {}
    if (container.get("Name") or "").lstrip("/") != STAGING_CONTAINER:
        errors.append("unexpected_container_identity")
    if host.get("NetworkMode") != STAGING_NETWORK or set(docker_networks) != {STAGING_NETWORK}:
        errors.append("network_namespace_not_isolated")
    if network.get("Name") != STAGING_NETWORK or network.get("Driver") != "bridge":
        errors.append("staging_network_not_dedicated_bridge")
    if (network.get("Labels") or {}).get("goreecloud.role") != "search-staging-egress":
        errors.append("staging_network_label_unverified")
    if host.get("Privileged") is not False:
        errors.append("privileged_container")
    if host.get("ReadonlyRootfs") is not True:
        errors.append("writable_root_filesystem")
    if host.get("CapAdd"):
        errors.append("additional_linux_capabilities")
    if "ALL" not in [str(cap).upper() for cap in host.get("CapDrop") or []]:
        errors.append("capabilities_not_dropped")
    if "no-new-privileges" not in [str(opt).lower() for opt in host.get("SecurityOpt") or []]:
        errors.append("new_privileges_not_blocked")
    if (cfg.get("User") or "").split(":")[0] in ("", "root", "0"):
        errors.append("container_user_is_root")
    if (host.get("PidMode") not in ("", None, "private")
            or host.get("IpcMode") not in ("", None, "private")
            or host.get("UsernsMode") == "host"):
        errors.append("shared_host_namespace")
    if host.get("NetworkMode") in ("host", "container", "bridge", "default"):
        errors.append("shared_network_mode")
    if host.get("Binds") or container.get("Mounts") or host.get("Devices"):
        errors.append("unexpected_host_mounts_or_devices")
    if host.get("ExtraHosts"):
        errors.append("host_resolution_override")
    if host.get("PublishAllPorts") or host.get("PortBindings") or net.get("Ports"):
        errors.append("public_or_bound_ports")
    if network.get("Internal") is True:
        errors.append("network_has_no_provider_egress")
    memory = host.get("Memory")
    if not isinstance(memory, int) or not (64 * 1024 * 1024 <= memory <= 512 * 1024 * 1024):
        errors.append("memory_limit_missing_or_oversized")
    pids = host.get("PidsLimit")
    if not isinstance(pids, int) or not (8 <= pids <= 128):
        errors.append("pid_limit_missing_or_oversized")
    nano_cpus = host.get("NanoCpus")
    if not isinstance(nano_cpus, int) or not (100_000_000 <= nano_cpus <= 1_000_000_000):
        errors.append("cpu_limit_missing_or_oversized")
    if host.get("AutoRemove") is not True:
        errors.append("ephemeral_teardown_not_enabled")
    return errors


def _inspect(kind: str, name: str):
    result = subprocess.run(
        ["docker", kind, "inspect", name] if kind == "network" else ["docker", "inspect", name],
        check=True, capture_output=True, text=True, timeout=10,
    )
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise ValueError("invalid Docker inspection result")
    return parsed[0]


def main():
    p = argparse.ArgumentParser(description="Read-only preflight for isolated private Search staging")
    p.add_argument("--container", default=STAGING_CONTAINER,
                   choices=[STAGING_CONTAINER], help="Only the dedicated staging container is permitted")
    args = p.parse_args()
    try:
        container = _inspect("container", args.container)
        network = _inspect("network", STAGING_NETWORK)
        failed = evaluate(container, network)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("NOT_QUALIFIED: staging inspection unavailable")
        raise SystemExit(2)
    if failed:
        print("NOT_QUALIFIED: " + ",".join(sorted(set(failed))))
        raise SystemExit(1)
    print("CONTAINER_CONFIG_PASS: dedicated rootless-like restrictions present")
    print("NOT_QUALIFIED: network egress firewall, real DNS/metadata denial, and visitor IP masking unverified")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
