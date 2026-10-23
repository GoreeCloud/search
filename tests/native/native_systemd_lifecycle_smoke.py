#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exercise the owned service as an *actual* temporary Linux systemd unit.

This test is restricted to an ephemeral GitHub-hosted Ubuntu runner. It never
installs or enables the canonical unit on a managed host, uses only synthetic
index data and loopback, and removes its /run test unit after exercising the
system manager's start, crash-restart, stop and failure handling.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import pwd
import grp
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from native_search.index import SearchIndex
from scripts.build_native_linux_service import MANIFEST_NAME, SERVICE_FILES


UNIT_SOURCE = ROOT / "deploy/native-linux/goreecloud-search-native.service"
UNIT_DIRECTORY = Path("/run/systemd/system")
RUNTIME_DIRECTORY = Path("/run")
SOURCE_ARCHIVE = Path("/opt/goreecloud-search-native/search-native.pyz")
SOURCE_DATABASE = Path("/var/lib/goreecloud-search-native/index.db")
SOURCE_DIRECTORY = Path("/var/lib/goreecloud-search-native")
SOURCE_EXEC = ("ExecStart=/usr/bin/python3 " + str(SOURCE_ARCHIVE) +
               " --db " + str(SOURCE_DATABASE) + " --port 8789")


class LifecycleBlocked(Exception):
    """The ephemeral system manager cannot safely qualify the candidate."""


class LifecycleWithTeardownFailure(LifecycleBlocked):
    """Carry the original stage separately from cleanup, never raw details."""

    def __init__(self, primary: Exception):
        self.primary = primary
        super().__init__("teardown")


# The CI log is intentionally limited to these fixed, non-content categories.
# Never print arbitrary subprocess output, exceptions, paths, source, or data.
DIAGNOSTIC_STAGES = frozenset((
    "host", "provenance", "fixture", "unit-render", "unit-create",
    "unit-verify", "manager-reload", "unit-identity", "start", "readiness",
    "query", "process-identity", "failure-injection", "restart", "stop",
    "missing-index", "restore", "listener-closed", "teardown",
    "teardown-inspect", "teardown-stop", "teardown-confirm",
    "teardown-reset", "teardown-unlink", "teardown-reload", "unknown",
))


@contextmanager
def _stage(name: str):
    """Collapse arbitrary errors to a stable, non-sensitive failure category."""
    if name not in DIAGNOSTIC_STAGES:
        raise AssertionError("diagnostic category must be allowlisted")
    try:
        yield
    except (LifecycleBlocked, OSError, ValueError, KeyError, TypeError,
            subprocess.TimeoutExpired):
        raise LifecycleBlocked(name) from None


def blocked_message(error: Exception) -> str:
    """Output never includes exception text unless it is a fixed stage token."""
    if isinstance(error, LifecycleWithTeardownFailure):
        primary = _safe_stage(error.primary)
        return (f"NATIVE_SYSTEMD_LIFECYCLE_BLOCKED primary={primary} "
                "cleanup=teardown: no managed-service acceptance\n")
    stage = _safe_stage(error)
    return f"NATIVE_SYSTEMD_LIFECYCLE_BLOCKED stage={stage}: no managed-service acceptance\n"


def _safe_stage(error: Exception) -> str:
    diagnostic = str(error) if isinstance(error, LifecycleBlocked) else "unknown"
    return diagnostic if diagnostic in DIAGNOSTIC_STAGES else "unknown"


def _run(*args: str, accepted: tuple[int, ...] = (0,), timeout: int = 20) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise LifecycleBlocked("systemd management command unavailable or timed out") from None
    if result.returncode not in accepted:
        # Never echo arbitrary systemd journal/output, paths or private content.
        raise LifecycleBlocked("systemd management command rejected the disposable unit")
    return result.stdout.strip()


def _replace_once(source: str, old: str, replacement: str) -> str:
    if source.count(old) != 1:
        raise LifecycleBlocked("canonical native service unit changed unexpectedly")
    return source.replace(old, replacement, 1)


def render_temporary_unit(template: str, directory: Path, archive: Path,
                          database: Path, port: int) -> str:
    """Preserve the actual service protections while rebasing only fixture paths.

    No arbitrary unit text is accepted from command-line input. This function
    requires the canonical fixed-user and path template to remain recognizable.
    """
    if not 1 <= port <= 65535:
        raise LifecycleBlocked("invalid disposable port")
    edits = (
        ("User=goreecloud-search", "User=nobody"),
        ("Group=goreecloud-search", "Group=nogroup"),
        (f"WorkingDirectory={SOURCE_DIRECTORY}", f"WorkingDirectory={directory}"),
        (f"ConditionPathExists={SOURCE_DATABASE}", f"ConditionPathExists={database}"),
        (f"ReadWritePaths={SOURCE_DIRECTORY}", f"ReadWritePaths={directory}"),
        (SOURCE_EXEC,
         f"ExecStart=/usr/bin/python3 -I -B {archive} --db {database} --port {port}"),
    )
    result = template
    for old, new in edits:
        result = _replace_once(result, old, new)
    active_lines = [line.strip() for line in result.splitlines()
                    if line.strip() and not line.lstrip().startswith(("#", ";"))]
    for security in ("NoNewPrivileges=yes", "ProtectSystem=strict", "ProtectHome=yes",
                     "PrivateTmp=yes", "IPAddressDeny=any", "IPAddressAllow=localhost",
                     "RestrictAddressFamilies=AF_INET AF_UNIX", "CapabilityBoundingSet=",
                     "Restart=on-failure"):
        if active_lines.count(security) != 1:
            raise LifecycleBlocked("canonical native service security directive changed")
    if "[Install]" in active_lines or any(line.startswith("WantedBy=") for line in active_lines):
        raise LifecycleBlocked("canonical service gained an enablement path")
    return result


def _require_ephemeral_host() -> None:
    if (sys.platform != "linux" or os.geteuid() != 0
            or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"):
        raise LifecycleBlocked("real systemd acceptance requires a privileged GitHub-hosted Linux runner")
    try:
        init = Path("/proc/1/comm").read_text(encoding="ascii").strip()
    except OSError:
        init = ""
    if init != "systemd" or not UNIT_DIRECTORY.is_dir():
        raise LifecycleBlocked("ephemeral runner does not expose a real systemd manager")
    if any(shutil.which(binary) is None for binary in ("systemctl", "systemd-analyze")):
        raise LifecycleBlocked("systemd lifecycle tooling is not available")


def _validate_archive(archive: Path, expected_sha: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise LifecycleBlocked("expected exact commit is malformed")
    if archive.is_symlink() or not archive.is_file() or archive.suffix != ".pyz":
        raise LifecycleBlocked("exact candidate archive missing or ambiguous")
    if archive.stat().st_size > 1_000_000:
        raise LifecycleBlocked("native candidate archive is unexpectedly large")
    try:
        with ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read(MANIFEST_NAME))
            if set(bundle.namelist()) != {*SERVICE_FILES, "__main__.py", MANIFEST_NAME}:
                raise LifecycleBlocked("candidate archive exceeds native-only allowlist")
            if len(bundle.namelist()) != len(SERVICE_FILES) + 2:
                raise LifecycleBlocked("candidate archive includes duplicate members")
            if manifest.get("source_sha256") != {
                    name: sha256(bundle.read(name)).hexdigest() for name in SERVICE_FILES}:
                raise LifecycleBlocked("candidate source hashes do not match archive")
    except (OSError, ValueError, KeyError, BadZipFile, TypeError):
        raise LifecycleBlocked("native candidate build identity is malformed") from None
    if (manifest.get("repository") != "https://github.com/GoreeCloud/search"
            or manifest.get("source_commit") != expected_sha
            or manifest.get("mode") != "development_loopback_service_only"):
        raise LifecycleBlocked("candidate manifest differs from exact authorized source")


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(port: int, method: str, path: str, data: bytes | None = None) -> tuple[int, bytes]:
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        client.request(method, path, body=data, headers={
            "Host": f"127.0.0.1:{port}", "Content-Type": "application/json"})
        response = client.getresponse()
        return response.status, response.read()
    finally:
        client.close()


def _show(unit: str, property_name: str) -> str:
    value = _run("systemctl", "show", "--property=" + property_name,
                 "--value", unit)
    if not value:
        raise LifecycleBlocked("systemd did not report required unit state")
    return value


def _wait_healthy(unit: str, port: int, prior_pid: int = 0, seconds: float = 25.0) -> int:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        pid = int(_show(unit, "MainPID"))
        if pid > 0 and pid != prior_pid and _show(unit, "ActiveState") == "active":
            try:
                status, body = _request(port, "GET", "/healthz")
                if status == 200 and json.loads(body) == {
                    "status": "ok", "mode": "native-development"}:
                    return pid
            except (OSError, ValueError):
                pass
        time.sleep(0.15)
    raise LifecycleBlocked("OS-managed native service failed readiness or restart deadline")


def _assert_unprivileged_process(pid: int, uid: int, gid: int) -> None:
    """Check actual OS process identity; systemctl User= alone is insufficient."""
    status = Path(f"/proc/{pid}/status").read_text(encoding="ascii")
    lines = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    user_ids = [int(value) for value in lines.get("Uid", "").split()]
    group_ids = [int(value) for value in lines.get("Gid", "").split()]
    if len(user_ids) != 4 or any(value != uid for value in user_ids):
        raise LifecycleBlocked("actual systemd service user is not unprivileged")
    if len(group_ids) != 4 or any(value != gid for value in group_ids):
        raise LifecycleBlocked("actual systemd service group is not unprivileged")


def _cleanup_created_unit(unit: str, unit_path: Path) -> None:
    """Tear down only our unit, including a unit never loaded by systemd.

    Verifying the system manager reports no active processes is required before
    unlinking. An unrecognized/failed manager state fails closed and leaves
    the unit in the short-lived runner for investigation, not on a VPS.
    """
    with _stage("teardown-inspect"):
        if unit_path.is_symlink() or not unit_path.is_file():
            raise LifecycleBlocked("disposable unit path is not our regular file")
        load_state = _show(unit, "LoadState")
        active_state = _show(unit, "ActiveState")
        main_pid = int(_show(unit, "MainPID"))
        control_pid = int(_show(unit, "ControlPID"))
        if load_state not in ("loaded", "not-found", "bad-setting", "error", "masked"):
            raise LifecycleBlocked("systemd reports an unrecognized unit load state")
        if active_state not in ("active", "activating", "reloading", "deactivating",
                                "inactive", "failed"):
            raise LifecycleBlocked("systemd reports an unrecognized unit active state")
        if main_pid < 0 or control_pid < 0:
            raise LifecycleBlocked("systemd reported an invalid native unit process")

    # If verify/reload failed before systemd loaded the file, show reports
    # not-found/inactive/PIDs=0. There is nothing to stop; a stop request for
    # an unknown unit can itself fail and previously masked the actual gate.
    if active_state not in ("inactive", "failed") or main_pid or control_pid:
        with _stage("teardown-stop"):
            try:
                _run("systemctl", "stop", unit)
            except LifecycleBlocked:
                _run("systemctl", "kill", "--signal=SIGKILL",
                     "--kill-whom=all", unit, accepted=(0, 1))
                _run("systemctl", "stop", unit)

    with _stage("teardown-confirm"):
        after_state = _show(unit, "ActiveState")
        after_main = int(_show(unit, "MainPID"))
        after_control = int(_show(unit, "ControlPID"))
        if after_state not in ("inactive", "failed") or after_main != 0 or after_control != 0:
            raise LifecycleBlocked("disposable unit still has unaccounted processes")
    # reset-failed is for a genuinely failed unit, not an already stopped,
    # healthy transient unit. Some hosted systemd versions reject resetting
    # an inactive unit with no recorded failure.
    if load_state == "loaded" and after_state == "failed":
        with _stage("teardown-reset"):
            _run("systemctl", "reset-failed", unit)
    with _stage("teardown-unlink"):
        unit_path.unlink()
    with _stage("teardown-reload"):
        _run("systemctl", "daemon-reload")


def _teardown_preserving_primary(unit: str, unit_path: Path) -> None:
    """Prevent cleanup failure from overwriting a more informative stage."""
    primary = sys.exc_info()[1]
    try:
        _cleanup_created_unit(unit, unit_path)
    except (LifecycleBlocked, OSError, ValueError, TypeError, KeyError,
            subprocess.TimeoutExpired) as error:
        if primary is not None:
            raise LifecycleWithTeardownFailure(primary) from None
        if isinstance(error, LifecycleBlocked) and str(error) in DIAGNOSTIC_STAGES:
            raise
        raise LifecycleBlocked("teardown") from None


def exercise(archive: Path, expected_sha: str) -> None:
    with _stage("host"):
        _require_ephemeral_host()
    with _stage("provenance"):
        _validate_archive(archive, expected_sha)
    with _stage("fixture"):
        template = UNIT_SOURCE.read_text(encoding="utf-8")
        nobody = pwd.getpwnam("nobody").pw_uid
        nogroup = grp.getgrnam("nogroup").gr_gid
    unit = f"goreecloud-native-ci-{secrets.token_hex(6)}.service"
    unit_path = UNIT_DIRECTORY / unit
    installed = False
    with tempfile.TemporaryDirectory(prefix="gc-search-native-ci-", dir=RUNTIME_DIRECTORY) as tmp:
        with _stage("fixture"):
            directory = Path(tmp)
            staged_bundle = directory / "search-native.pyz"
            database = directory / "index.db"
            shutil.copyfile(archive, staged_bundle)
            with SearchIndex(database) as index:
                index.add(url="https://example.org/native-fixture", title="Synthetic Native Fixture",
                          body="Disposably managed by Linux systemd without upstream providers")
            os.chown(directory, nobody, nogroup)
            os.chmod(directory, 0o700)
            for owned in (staged_bundle, database):
                os.chown(owned, nobody, nogroup)
                os.chmod(owned, 0o600)
            port = _reserve_port()
        with _stage("unit-render"):
            unit_text = render_temporary_unit(template, directory, staged_bundle, database, port)
        try:
            # O_EXCL protects any preexisting unrelated unit even if a random
            # identifier unexpectedly collides. /run is volatile, not /etc.
            with _stage("unit-create"):
                descriptor = os.open(unit_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                installed = True
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(unit_text)
            with _stage("unit-verify"):
                _run("systemd-analyze", "verify", str(unit_path))
            with _stage("manager-reload"):
                _run("systemctl", "daemon-reload")
            with _stage("unit-identity"):
                if _show(unit, "FragmentPath") != str(unit_path):
                    raise LifecycleBlocked("systemd loaded a different native unit")
            with _stage("start"):
                _run("systemctl", "start", unit)
            with _stage("readiness"):
                first_pid = _wait_healthy(unit, port)
            with _stage("process-identity"):
                _assert_unprivileged_process(first_pid, nobody, nogroup)
            with _stage("query"):
                status, body = _request(port, "POST", "/v1/search", b'{"query":"disposably"}')
                if (status != 200 or json.loads(body).get("total_displayed") != 1):
                    raise LifecycleBlocked("systemd service did not return owned fixture search")
            with _stage("unit-identity"):
                if _show(unit, "User") != "nobody" or _show(unit, "Restart") != "on-failure":
                    raise LifecycleBlocked("systemd did not apply the test identity or restart policy")
            with _stage("failure-injection"):
                _run("systemctl", "kill", "--signal=SIGKILL", "--kill-whom=main", unit)
            with _stage("restart"):
                restarted_pid = _wait_healthy(unit, port, prior_pid=first_pid)
                _assert_unprivileged_process(restarted_pid, nobody, nogroup)
            with _stage("stop"):
                _run("systemctl", "stop", unit)
                if _show(unit, "ActiveState") != "inactive":
                    raise LifecycleBlocked("systemd did not cleanly stop the native service")

            # A missing approved index MUST fail closed. This checks the
            # actual unit's ConditionPathExists, not an emulated error path.
            with _stage("missing-index"):
                absent_db = directory / "index-db-temporarily-absent"
                database.rename(absent_db)
                try:
                    _run("systemctl", "start", unit)
                    if (_show(unit, "ConditionResult") != "no"
                            or _show(unit, "ActiveState") != "inactive"):
                        raise LifecycleBlocked("missing index did not block OS-managed service")
                finally:
                    absent_db.rename(database)

            # Restore a real fixture and show that OS management can resume.
            with _stage("restore"):
                _run("systemctl", "start", unit)
                restored_pid = _wait_healthy(unit, port)
                _assert_unprivileged_process(restored_pid, nobody, nogroup)
                _run("systemctl", "stop", unit)
            with _stage("listener-closed"):
                try:
                    _request(port, "GET", "/healthz")
                except OSError:
                    pass
                else:
                    raise LifecycleBlocked("stopped systemd service still accepts requests")
        finally:
            if installed:
                _teardown_preserving_primary(unit, unit_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        exercise(args.archive, args.expected_sha)
    except (LifecycleBlocked, OSError, ValueError, KeyError, PermissionError) as error:
        parser.exit(2, blocked_message(error))
    print("NATIVE_SYSTEMD_DISPOSABLE_PASS: real ephemeral systemd start/restart/stop; "
          "no installation, update, rollback, production or Anchor acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
