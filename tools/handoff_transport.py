from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Mapping

MACHINES = {"mac", "windows-wsl", "cloud"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HOST_RE = re.compile(r"^[A-Za-z0-9._:@-]+$")

CONFIG_KEYS = {
    "HANDOFF_PYTHON",
    "HANDOFF_MAC_HOST",
    "HANDOFF_WINDOWS_HOST",
    "HANDOFF_CLOUD_HOST",
    "HANDOFF_MAC_REPO",
    "HANDOFF_WINDOWS_REPO",
    "HANDOFF_CLOUD_REPO",
    "HANDOFF_BUNDLE_DIR",
}

DEFAULT_REPOS = {
    "mac": "/Users/windellereboquio/AstraHandoff/emailautomation",
    "windows-wsl": "/home/jc/src/emailautomation",
    "cloud": "/opt/astra/emailautomation",
}
class TransportError(RuntimeError):
    pass


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            text=True,
            capture_output=capture,
            check=True,
        )
    except FileNotFoundError as exc:
        raise TransportError(f"Required command is unavailable: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise TransportError(f"Command failed ({args[0]}){suffix}") from exc


def _parse_config_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    parsed: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in CONFIG_KEYS:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        parsed[key] = value
    return parsed


def load_config(
    repo: Path,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    user_home = home or Path(env.get("HOME") or Path.home())
    configured = env.get("HANDOFF_CONFIG_FILE", "").strip()
    global_path = (
        Path(configured).expanduser()
        if configured
        else user_home / ".config" / "astra" / "handoff.env"
    )
    local_path = repo / ".handoff.local"

    values: dict[str, str] = {}
    values.update(_parse_config_file(global_path))
    values.update(_parse_config_file(local_path))
    for key in CONFIG_KEYS:
        if env.get(key, "").strip():
            values[key] = env[key].strip()

    values.setdefault("HANDOFF_PYTHON", sys.executable or "python3")
    values.setdefault("HANDOFF_MAC_HOST", "")
    values.setdefault("HANDOFF_WINDOWS_HOST", "")
    values.setdefault("HANDOFF_CLOUD_HOST", "")
    values.setdefault("HANDOFF_MAC_REPO", DEFAULT_REPOS["mac"])
    values.setdefault("HANDOFF_WINDOWS_REPO", DEFAULT_REPOS["windows-wsl"])
    values.setdefault("HANDOFF_CLOUD_REPO", DEFAULT_REPOS["cloud"])
    values.setdefault("HANDOFF_BUNDLE_DIR", str(repo / "runtime_handoff_bundles"))
    values["_GLOBAL_CONFIG_FILE"] = str(global_path)
    values["_LOCAL_CONFIG_FILE"] = str(local_path)
    return values


def endpoint(config: Mapping[str, str], target: str) -> tuple[str, str]:
    if target not in MACHINES:
        raise TransportError(f"Unsupported target machine: {target}")
    prefix = "WINDOWS" if target == "windows-wsl" else target.upper()
    host = config[f"HANDOFF_{prefix}_HOST"].strip()
    repo = config[f"HANDOFF_{prefix}_REPO"].strip()
    if not host:
        raise TransportError(
            f"No SSH host configured for {target}. "
            "Use .handoff.local or ~/.config/astra/handoff.env."
        )
    if not HOST_RE.fullmatch(host):
        raise TransportError(f"Unsafe SSH host value for {target}")
    posix_repo = PurePosixPath(repo)
    if not repo or not posix_repo.is_absolute() or "'" in repo or "\n" in repo:
        raise TransportError(f"Unsafe target repository path for {target}")
    return host, repo
def _git(repo: Path, *args: str) -> str:
    return _run(["git", *args], cwd=repo).stdout.strip()


def _runtime_status(repo: Path, python_bin: str, *, machine: str | None = None) -> dict:
    cmd = [
        python_bin,
        str(repo / "tools" / "runtime_handoff.py"),
        "--repo",
        str(repo),
    ]
    env = os.environ.copy()
    if machine:
        env["ASTRA_MACHINE_ID"] = machine
    try:
        result = subprocess.run(
            cmd + ["status"],
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or ""
        raise TransportError(f"Unable to read runtime status: {detail.strip()}") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TransportError("Runtime status returned invalid JSON") from exc


def source_identity(repo: Path, config: Mapping[str, str]) -> tuple[str, str]:
    if _git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise TransportError("Tracked source worktree is dirty")
    branch = _git(repo, "branch", "--show-current")
    head = _git(repo, "rev-parse", "HEAD")
    if not branch:
        raise TransportError("Source repository is detached")
    if not SHA_RE.fullmatch(head):
        raise TransportError("Source HEAD is malformed")

    published = _git(repo, "ls-remote", "origin", f"refs/heads/{branch}")
    remote_head = published.split()[0] if published else ""
    if remote_head != head:
        raise TransportError(
            "Source HEAD is not published to "
            f"origin/{branch} (local={head}, remote={remote_head or 'missing'})"
        )

    status = _runtime_status(repo, config["HANDOFF_PYTHON"])
    if status.get("process_blockers"):
        raise TransportError("Source runtime process is active")
    if status.get("active_job_files"):
        raise TransportError("Source runtime job is active")
    if status.get("real_send_authorized") is not True:
        raise TransportError("Source is not the currently authorized sender machine")
    return branch, head


def _ssh(host: str, script: str, *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    remote = f"bash -lc {shlex.quote(script)}"
    return _run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, remote],
        capture=capture,
    )
def _remote_sync_status(
    host: str,
    remote_repo: str,
    target: str,
    branch: str,
    head: str,
) -> dict:
    qrepo = shlex.quote(remote_repo)
    qbranch = shlex.quote(branch)
    qhead = shlex.quote(head)
    qtarget = shlex.quote(target)
    script = f"""set -euo pipefail
cd {qrepo}
test -z "$(git status --porcelain --untracked-files=no)" || {{
  echo "REFUSED: tracked target worktree is dirty." >&2; exit 41;
}}
test "$(git branch --show-current)" = {qbranch} || {{
  echo "REFUSED: target branch mismatch." >&2; exit 42;
}}
git fetch --quiet origin {qbranch}
git cat-file -e {qhead}^{{commit}}
current="$(git rev-parse HEAD)"
if [ "$current" != {qhead} ]; then
  git merge-base --is-ancestor "$current" {qhead} || {{
    echo "REFUSED: target code diverged." >&2; exit 44;
  }}
  git merge --ff-only {qhead} >/dev/null
fi
test "$(git rev-parse HEAD)" = {qhead}
ASTRA_MACHINE_ID={qtarget} ./handoff status
"""
    result = _ssh(host, script)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TransportError("Target preflight returned invalid status JSON") from exc
def validate_preflight_status(status: Mapping[str, object], head: str) -> None:
    if status.get("head") != head:
        raise TransportError("Target HEAD mismatch after code synchronization")
    if status.get("process_blockers"):
        raise TransportError("Target runtime process is active")
    if status.get("active_job_files"):
        raise TransportError("Target runtime job is active")
    authority = status.get("authority") or {}
    if isinstance(authority, Mapping) and authority.get("status") == "active":
        raise TransportError("Target authority is already active")
    if status.get("authority_error"):
        raise TransportError(f"Target authority error: {status['authority_error']}")


def _export_bundle(
    repo: Path,
    config: Mapping[str, str],
    target: str,
) -> Path:
    output_dir = Path(config["HANDOFF_BUNDLE_DIR"]).expanduser()
    cmd = [
        config["HANDOFF_PYTHON"],
        str(repo / "tools" / "runtime_handoff.py"),
        "--repo",
        str(repo),
        "export",
        "--target",
        target,
        "--output-dir",
        str(output_dir),
    ]
    result = _run(cmd)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise TransportError("Runtime export did not return a bundle path")
    bundle = Path(lines[-1])
    if not bundle.is_file():
        raise TransportError(f"Runtime bundle was not created: {bundle}")
    return bundle
def _remote_receive(
    host: str,
    remote_repo: str,
    target: str,
    bundle: Path,
) -> str:
    remote_bundle = f"/tmp/{bundle.name}"
    remote_part = f"{remote_bundle}.part"
    _run(["scp", "-p", str(bundle), f"{host}:{remote_part}"], capture=False)
    _ssh(
        host,
        f"chmod 600 {shlex.quote(remote_part)} && "
        f"mv {shlex.quote(remote_part)} {shlex.quote(remote_bundle)}",
        capture=False,
    )
    receive = (
        f"cd {shlex.quote(remote_repo)} && "
        f"ASTRA_MACHINE_ID={shlex.quote(target)} "
        f"./handoff receive {shlex.quote(remote_bundle)}"
    )
    _ssh(host, receive, capture=False)
    return remote_bundle


def _remote_status(host: str, remote_repo: str, target: str) -> dict:
    script = (
        f"cd {shlex.quote(remote_repo)} && "
        f"ASTRA_MACHINE_ID={shlex.quote(target)} ./handoff status"
    )
    result = _ssh(host, script)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TransportError("Target verification returned invalid status JSON") from exc


def validate_activation_status(status: Mapping[str, object], target: str, head: str) -> None:
    authority = status.get("authority") or {}
    if not isinstance(authority, Mapping):
        raise TransportError("Target authority is missing after handoff")
    checks = {
        "target HEAD": status.get("head") == head,
        "authority commit": authority.get("expected_git_commit") == head,
        "authority machine": authority.get("authorized_machine") == target,
        "authority status": authority.get("status") == "active",
        "real-send authorization": status.get("real_send_authorized") is True,
        "no runtime processes": not status.get("process_blockers"),
        "no active jobs": not status.get("active_job_files"),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise TransportError("Target verification failed: " + ", ".join(failed))


def switch(repo: Path, config: Mapping[str, str], target: str) -> None:
    host, remote_repo = endpoint(config, target)
    branch, head = source_identity(repo, config)

    print(f"Preflighting {target} before source authorization is changed...")
    preflight = _remote_sync_status(host, remote_repo, target, branch, head)
    validate_preflight_status(preflight, head)

    bundle: Path | None = None
    remote_bundle = ""
    try:
        bundle = _export_bundle(repo, config, target)
        print("Source is now unauthorized. Transferring verified runtime bundle...")
        remote_bundle = _remote_receive(host, remote_repo, target, bundle)
        activated = _remote_status(host, remote_repo, target)
        validate_activation_status(activated, target, head)
        _ssh(host, f"rm -f {shlex.quote(remote_bundle)}", capture=False)
    except Exception:
        print(
            "HANDOFF INCOMPLETE. The source remains unauthorized by design. "
            "Do not start a sender until status is reconciled.",
            file=sys.stderr,
        )
        if bundle is not None:
            print(f"Local bundle retained at: {bundle}", file=sys.stderr)
        if remote_bundle:
            print(f"Remote bundle retained at: {host}:{remote_bundle}", file=sys.stderr)
        raise

    print(f"Handoff complete: {target} is authorized at {head}.")
    print("No sender was started. Start sending only when you choose to.")


def show_config(repo: Path, config: Mapping[str, str]) -> None:
    local_file = Path(config["_LOCAL_CONFIG_FILE"])
    global_file = Path(config["_GLOBAL_CONFIG_FILE"])
    print(f"repo_root={repo}")
    print(f"config_local={local_file} loaded={local_file.is_file()}")
    print(f"config_global={global_file} loaded={global_file.is_file()}")
    for target in ("mac", "windows-wsl", "cloud"):
        prefix = "WINDOWS" if target == "windows-wsl" else target.upper()
        host = config[f"HANDOFF_{prefix}_HOST"] or "<not configured>"
        target_repo = config[f"HANDOFF_{prefix}_REPO"]
        print(f"{target}_host={host}")
        print(f"{target}_repo={target_repo}")


def doctor(repo: Path, config: Mapping[str, str], target: str | None) -> None:
    show_config(repo, config)
    print("local_runtime_status=")
    print(json.dumps(_runtime_status(repo, config["HANDOFF_PYTHON"]), indent=2))
    if target is None:
        return
    host, remote_repo = endpoint(config, target)
    probe = (
        f"cd {shlex.quote(remote_repo)} && "
        "printf 'branch=' && git branch --show-current && "
        "printf 'head=' && git rev-parse HEAD && "
        "printf 'tracked_changes=' && "
        "git status --porcelain --untracked-files=no | wc -l && "
        f"ASTRA_MACHINE_ID={shlex.quote(target)} ./handoff status"
    )
    result = _ssh(host, probe)
    print(f"target_probe_{target}=")
    print(result.stdout.rstrip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    switch_parser = commands.add_parser("switch")
    switch_parser.add_argument("--target", choices=sorted(MACHINES), required=True)
    commands.add_parser("config")
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--target", choices=sorted(MACHINES))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    config = load_config(repo)
    try:
        if args.command == "switch":
            switch(repo, config, args.target)
        elif args.command == "config":
            show_config(repo, config)
        elif args.command == "doctor":
            doctor(repo, config, args.target)
        return 0
    except TransportError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
