#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only release admission for a parallel free Search upgrade on GoreeCloud VPS.

Never creates config, reloads Caddy, changes Docker state, probes a provider,
prints secrets or auto-promotes a release. Fail closed if any gate is unknown.
"""
from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
from pathlib import Path

import yaml

OLD = "goreecloud-search-free-canary-gateway:8080"
NEW = "goreecloud-search-free-upgrade-gateway:8080"
OLD_SEARCH = "goreecloud-search-free-canary-search-1"
OLD_INGRESS = "goreecloud-search-free-canary-ingress-1"
NEW_SEARCH = "goreecloud-search-free-upgrade-search-1"
NEW_INGRESS = "goreecloud-search-free-upgrade-ingress-1"
HOST = "search-dev.goreecloud.com"
PROJECT = "goreecloud-search-free-upgrade"
SHA = re.compile(r"[0-9a-f]{40}\Z")
IMAGE = re.compile(r"goreecloud/search:staging-[0-9a-f]{12}\Z")

PROFILE_IN_CONTAINER = "/usr/local/searxng/free-settings.yml"
PROFILE_REPO_PATH = "configs/goreecloud/settings.free-first.yml"


def committed_profile(revision: str) -> bytes | None:
    """Read exactly the profile committed at the intended image source SHA."""
    result = subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parents[1]), "show",
         revision + ":" + PROFILE_REPO_PATH],
        check=False, capture_output=True, timeout=8,
    )
    return result.stdout if result.returncode == 0 else None


def mounted_profile(container: dict | None) -> bytes | None:
    """Read only the upgrade container's declared read-only settings bind mount."""
    mounts = (container or {}).get("Mounts", [])
    matches = [
        m for m in mounts if isinstance(m, dict)
        and m.get("Destination") == PROFILE_IN_CONTAINER
        and m.get("Type") == "bind" and m.get("RW") is False
        and isinstance(m.get("Source"), str)
        and m["Source"].endswith("/" + PROFILE_REPO_PATH)
    ]
    if len(matches) != 1:
        return None
    source = Path(matches[0]["Source"])
    if source.is_symlink() or not source.is_file():
        return None
    return source.read_bytes()


def profile_is_safe(data: bytes | None) -> bool:
    if not data:
        return False
    try:
        profile = yaml.safe_load(data)
        if not isinstance(profile, dict):
            return False
        goreecloud = profile.get("goreecloud")
        outgoing = profile.get("outgoing")
        server = profile.get("server")
        if not all(isinstance(x, dict) for x in (goreecloud, outgoing, server)):
            return False
        return (
            type(goreecloud.get("request_budget_per_minute")) is int
            and goreecloud["request_budget_per_minute"] == 12
            and goreecloud.get("private_search") is True
            and goreecloud.get("require_anonymous_egress") is False
            and outgoing.get("proxies") == {}
            and outgoing.get("using_tor_proxy") is False
            and server.get("public_instance") is False
        )
    except yaml.YAMLError:
        return False


def inspect(name: str) -> dict | None:
    """Only docker inspect, never docker exec/run/reload/up."""
    result = subprocess.run(
        ["docker", "inspect", "--type", "container", name],
        check=False, capture_output=True, text=True, timeout=8,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    if not isinstance(data, list) or len(data) != 1:
        return None
    return data[0]


def image_inspect(tag: str) -> dict | None:
    result = subprocess.run(
        ["docker", "image", "inspect", tag],
        check=False, capture_output=True, text=True, timeout=8,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return data[0] if isinstance(data, list) and len(data) == 1 else None


def site_block(config: str) -> str | None:
    """Restrict assertions to the single Search host, never other sites."""
    header = HOST + " {"
    if config.count(header) != 1:
        return None
    rest = config.split(header, 1)[1]
    # Nested subblocks are allowed, but Caddy site closes at column zero.
    match = re.search(r"\n}", rest)
    return rest[:match.start()] if match else None


def evaluate(
    current: bytes | None, snapshot: bytes | None, mode_current: int | None,
    mode_snapshot: int | None, containers: dict, image: dict | None,
    expected_image: str, expected_sha: str,
    owner_current: int | None = None, owner_snapshot: int | None = None,
    profile_mounted: bytes | None = None, profile_committed: bytes | None = None,
) -> dict:
    checks: list[dict] = []

    def add(identifier: str, ok: bool, reason: str) -> None:
        checks.append({"check": identifier, "passed": bool(ok), "detail": reason})

    has_config = current is not None and mode_current == 0o600 and owner_current is not None
    add("protected_current_caddyfile", has_config, "requires an owned, private mode 0600 Caddyfile")
    add("rollback_file_owner_matches",
        owner_current is not None and owner_snapshot is not None
        and owner_snapshot == owner_current,
        "rollback snapshot must have the same owner UID as the current Caddyfile")
    text = current.decode("utf-8", "replace") if current is not None else ""
    block = site_block(text)
    old_route = "reverse_proxy " + OLD
    new_route = "reverse_proxy " + NEW
    add("unique_netbird_only_host", block is not None
        and "remote_ip 100.64.0.0/10" in block
        and 'respond "Forbidden" 403' in block,
        "single Search host must retain NetBird matcher and explicit 403")
    add("active_route_remains_old", block is not None
        and block.count(old_route) == 1 and new_route not in block
        and text.count(old_route) == 1 and text.count(new_route) == 0,
        "old free gateway must still be the sole live upstream")
    protected_snapshot = snapshot is not None and mode_snapshot == 0o600
    add("protected_exact_rollback_copy",
        protected_snapshot and snapshot == current,
        "fresh 0600 rollback snapshot must byte-match current Caddyfile")
    add("single_route_diff_can_be_reversed",
        block is not None and text.count(old_route) == 1
        and text.replace(old_route, new_route).replace(new_route, old_route) == text,
        "a proposed upgrade must change only the one Search upstream")

    old = containers.get(OLD_SEARCH)
    old_proxy = containers.get(OLD_INGRESS)
    new = containers.get(NEW_SEARCH)
    new_proxy = containers.get(NEW_INGRESS)

    def running(c: dict | None, health: bool = False) -> bool:
        return bool(c and c.get("State", {}).get("Status") == "running"
                    and (not health or c.get("State", {}).get("Health", {}).get("Status") == "healthy"))

    add("old_free_search_healthy", running(old, health=True), "existing free Search must remain healthy")
    add("old_free_ingress_running", running(old_proxy), "old ingress must remain available")
    add("upgrade_search_healthy", running(new, health=True), "parallel upgrade Search must be healthy")
    add("upgrade_ingress_running", running(new_proxy), "parallel upgrade ingress must be running")

    local_image_id = (image or {}).get("Id")
    add("upgrade_exact_image",
        bool(new and expected_image == "goreecloud/search:staging-" + expected_sha[:12]
             and new.get("Config", {}).get("Image") == expected_image
             and image and image.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision") == expected_sha),
        "running candidate tag and OCI source revision must match pinned head")
    add("running_image_id_matches_local_image",
        bool(new and isinstance(local_image_id, str)
             and re.fullmatch(r"sha256:[0-9a-f]{64}", local_image_id)
             and new.get("Image") == local_image_id),
        "the actual running container must use the pinned local image ID, not only a matching mutable tag")
    add("upgrade_project_identity",
        bool(new and new_proxy and
             all(c.get("Config", {}).get("Labels", {}).get("com.docker.compose.project") == PROJECT
                 for c in (new, new_proxy))),
        "upgrade must use a separate Compose project")

    expected_networks = {
        OLD_SEARCH: {"goreecloud-search-free-canary_app_link", "goreecloud-search-free-canary_provider_egress"},
        OLD_INGRESS: {"goreecloud-search-free-canary_app_link", "proxy"},
        NEW_SEARCH: {"goreecloud-search-free-upgrade_app_link", "goreecloud-search-free-upgrade_provider_egress"},
        NEW_INGRESS: {"goreecloud-search-free-upgrade_app_link", "proxy"},
    }
    for name, expected in expected_networks.items():
        c = containers.get(name)
        nets = c.get("NetworkSettings", {}).get("Networks", {}) if c else {}
        add("network_" + name.removeprefix("goreecloud-search-free-"),
            set(nets) == expected, "expected distinct, nonoverlapping Search/ingress networks")

    for name, c in ((OLD_SEARCH, old), (OLD_INGRESS, old_proxy),
                    (NEW_SEARCH, new), (NEW_INGRESS, new_proxy)):
        ports = (c or {}).get("NetworkSettings", {}).get("Ports") or {}
        ok = bool(c and c.get("HostConfig", {}).get("ReadonlyRootfs") is True
                  and not c.get("HostConfig", {}).get("PortBindings")
                  and all(not published for published in ports.values()))
        add("confined_" + name.removeprefix("goreecloud-search-free-"), ok,
            "container needs read-only root and zero host-published ports")

    def has_alias(c: dict | None, gateway: str) -> bool:
        proxy = (c or {}).get("NetworkSettings", {}).get("Networks", {}).get("proxy", {})
        return gateway in (proxy.get("Aliases") or [])
    add("distinct_old_gateway_alias", has_alias(old_proxy, OLD.split(":")[0]),
        "old gateway must retain unique proxy alias")
    add("distinct_new_gateway_alias", has_alias(new_proxy, NEW.split(":")[0]),
        "new gateway must use nonconflicting proxy alias")

    add("single_worker_budget",
        bool(new and {"GRANIAN_WORKERS=1"} <= set(new.get("Config", {}).get("Env", []))
             and {"SEARXNG_SETTINGS_PATH=" + PROFILE_IN_CONTAINER}
             <= set(new.get("Config", {}).get("Env", []))),
        "upgrade must retain one worker and load the inspected free settings path")
    add("pinned_readonly_free_profile",
        profile_mounted is not None and profile_committed is not None
        and profile_mounted == profile_committed and profile_is_safe(profile_committed),
        "mounted free settings must match the exact source revision and enforce 12/min, NetBird-only and no paid or Tor proxy")

    return {"status": "admitted_for_manual_cutover_review" if all(c["passed"] for c in checks)
            else "blocked_do_not_cutover", "checks": checks,
            "passed": sum(c["passed"] for c in checks), "total": len(checks)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only GoreeCloud free-search upgrade gate")
    p.add_argument("--image", required=True, help="Pinned local staging image")
    p.add_argument("--revision", required=True, help="Exact 40-character source SHA")
    p.add_argument("--caddyfile", type=Path, default=Path("/srv/docker/caddy/Caddyfile"))
    p.add_argument("--snapshot", type=Path,
                   default=Path("/srv/docker/caddy/Caddyfile.free-upgrade-snapshot"))
    args = p.parse_args(argv)
    if not IMAGE.fullmatch(args.image) or not SHA.fullmatch(args.revision):
        p.error("pin a valid GoreeCloud staging image and exact source revision")
    try:
        def read(path: Path):
            if not path.is_file() or path.is_symlink():
                return None, None, None
            metadata = path.stat()
            mode = stat.S_IMODE(metadata.st_mode)
            return path.read_bytes(), mode, metadata.st_uid

        active, mode_active, owner_active = read(args.caddyfile)
        old, mode_old, owner_old = read(args.snapshot)
        names = (OLD_SEARCH, OLD_INGRESS, NEW_SEARCH, NEW_INGRESS)
        containers = {n: inspect(n) for n in names}
        source_image = image_inspect(args.image)
        actual_profile = mounted_profile(containers.get(NEW_SEARCH))
        expected_profile = committed_profile(args.revision)
        outcome = evaluate(active, old, mode_active, mode_old, containers,
                           source_image, args.image, args.revision,
                           owner_current=owner_active, owner_snapshot=owner_old,
                           profile_mounted=actual_profile, profile_committed=expected_profile)
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        outcome = {"status": "blocked_do_not_cutover", "passed": 0, "total": 0,
                   "checks": [{"check": "inspection", "passed": False,
                               "detail": "one or more read-only inspections failed"}]}
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome["status"] == "admitted_for_manual_cutover_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
