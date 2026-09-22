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


def _best_effort_remote_cleanup(host: str, path: str) -> None:
    try:
        _ssh(host, f"rm -f {shlex.quote(path)}", capture=False)
    except TransportError as exc:
        print(
            f"WARNING: handoff succeeded but remote bundle cleanup failed: {exc}",
            file=sys.stderr,
        )


def _best_effort_local_cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        print(
            f"WARNING: handoff succeeded but local bundle cleanup failed: {exc}",
            file=sys.stderr,
        )


def _remote_source_identity(
    host: str,
    remote_repo: str,
    source: str,
) -> tuple[str, str, dict]:
    script = f"""set -euo pipefail
cd {shlex.quote(remote_repo)}
test -z "$(git status --porcelain --untracked-files=no)" || {{
  echo "REFUSED: tracked source worktree is dirty." >&2; exit 51;
}}
branch="$(git branch --show-current)"
test -n "$branch" || {{ echo "REFUSED: source is detached." >&2; exit 52; }}
head="$(git rev-parse HEAD)"
remote_head="$(git ls-remote origin "refs/heads/$branch" | awk 'NR==1 {{print $1}}')"
test "$remote_head" = "$head" || {{
  echo "REFUSED: source HEAD is not published." >&2; exit 53;
}}
printf '__HANDOFF_BRANCH__=%s\n' "$branch"
printf '__HANDOFF_HEAD__=%s\n' "$head"
ASTRA_MACHINE_ID={shlex.quote(source)} ./handoff status
"""
    result = _ssh(host, script)
    lines = result.stdout.splitlines()
    if len(lines) < 3 or not lines[0].startswith("__HANDOFF_BRANCH__="):
        raise TransportError("Remote source identity response is malformed")
    if not lines[1].startswith("__HANDOFF_HEAD__="):
        raise TransportError("Remote source identity response is malformed")
    branch = lines[0].split("=", 1)[1].strip()
    head = lines[1].split("=", 1)[1].strip()
    if not branch or not SHA_RE.fullmatch(head):
        raise TransportError("Remote source Git identity is malformed")
    try:
        status = json.loads("\n".join(lines[2:]))
    except json.JSONDecodeError as exc:
        raise TransportError("Remote source status returned invalid JSON") from exc
    return branch, head, status


def _sync_local_target(
    repo: Path,
    config: Mapping[str, str],
    *,
    target: str,
    branch: str,
    head: str,
) -> dict:
    if _git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise TransportError("Tracked target worktree is dirty")
    current_branch = _git(repo, "branch", "--show-current")
    if current_branch != branch:
        raise TransportError(
            f"Target branch is {current_branch or '<detached>'}, expected {branch}"
        )
    _run(["git", "fetch", "--quiet", "origin", branch], cwd=repo)
    try:
        _run(["git", "cat-file", "-e", f"{head}^{{commit}}"], cwd=repo)
    except TransportError as exc:
        raise TransportError("Target cannot resolve the published source commit") from exc

    current = _git(repo, "rev-parse", "HEAD")
    if current != head:
        try:
            _run(["git", "merge-base", "--is-ancestor", current, head], cwd=repo)
        except TransportError as exc:
            raise TransportError(
                "Target code is not a fast-forward ancestor of source; refusing takeover"
            ) from exc
        _run(["git", "merge", "--ff-only", head], cwd=repo)
    if _git(repo, "rev-parse", "HEAD") != head:
        raise TransportError("Target HEAD mismatch after code synchronization")

    status = _runtime_status(
        repo,
        config["HANDOFF_PYTHON"],
        machine=target,
    )
    validate_preflight_status(status, head)
    return status


def _remote_prepare_export(
    host: str,
    remote_repo: str,
    *,
    target: str,
) -> str:
    script = (
        f"cd {shlex.quote(remote_repo)} && "
        f"./handoff prepare-export {shlex.quote(target)}"
    )
    result = _ssh(host, script)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise TransportError("Remote runtime export did not return a bundle path")
    remote_bundle = lines[-1]
    path = PurePosixPath(remote_bundle)
    if not path.is_absolute() or ".." in path.parts or "\n" in remote_bundle:
        raise TransportError("Remote runtime bundle path is unsafe")
    return remote_bundle


def _pull_remote_bundle(host: str, remote_bundle: str, destination: Path) -> None:
    part = destination.with_name(destination.name + ".part")
    part.unlink(missing_ok=True)
    try:
        _run(["scp", "-p", f"{host}:{remote_bundle}", str(part)], capture=False)
        os.chmod(part, 0o600)
        os.replace(part, destination)
    finally:
        part.unlink(missing_ok=True)


def _local_receive(repo: Path, target: str, bundle: Path) -> None:
    env = os.environ.copy()
    env["ASTRA_MACHINE_ID"] = target
    try:
        subprocess.run(
            [str(repo / "handoff"), "receive", str(bundle)],
            cwd=repo,
            text=True,
            check=True,
            env=env,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise TransportError("Local runtime import failed") from exc


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
        _best_effort_remote_cleanup(host, remote_bundle)
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


def takeover_from(
    repo: Path,
    config: Mapping[str, str],
    *,
    source: str,
    target: str,
) -> None:
    if source == target:
        raise TransportError("Source and target machine must differ")
    host, remote_repo = endpoint(config, source)

    print(f"Inspecting {source} before any authorization changes...")
    branch, head, source_status = _remote_source_identity(
        host,
        remote_repo,
        source,
    )
    validate_activation_status(source_status, source, head)

    print(f"Synchronizing local {target} code to {head[:7]} before takeover...")
    _sync_local_target(
        repo,
        config,
        target=target,
        branch=branch,
        head=head,
    )

    bundle: Path | None = None
    remote_bundle = ""
    try:
        remote_bundle = _remote_prepare_export(
            host,
            remote_repo,
            target=target,
        )
        print("Source is now unauthorized. Pulling verified runtime bundle...")
        local_dir = Path(config["HANDOFF_BUNDLE_DIR"]).expanduser()
        local_dir.mkdir(parents=True, exist_ok=True)
        bundle = local_dir / Path(remote_bundle).name
        if bundle.exists():
            raise TransportError(f"Local runtime bundle already exists: {bundle}")
        _pull_remote_bundle(host, remote_bundle, bundle)
        _local_receive(repo, target, bundle)
        activated = _runtime_status(
            repo,
            config["HANDOFF_PYTHON"],
            machine=target,
        )
        validate_activation_status(activated, target, head)
        _best_effort_remote_cleanup(host, remote_bundle)
        _best_effort_local_cleanup(bundle)
    except Exception:
        print(
            "TAKEOVER INCOMPLETE. The source remains unauthorized if export "
            "already started. Do not start either sender until status is reconciled.",
            file=sys.stderr,
        )
        if remote_bundle:
            print(f"Remote bundle retained at: {host}:{remote_bundle}", file=sys.stderr)
        if bundle is not None and bundle.exists():
            print(f"Local bundle retained at: {bundle}", file=sys.stderr)
        raise

    print(f"Takeover complete: {target} is authorized at {head}.")
    print("No sender was started. Start sending only when you choose to.")


def prepare_export(
    repo: Path,
    config: Mapping[str, str],
    *,
    target: str,
) -> Path:
    source_identity(repo, config)
    return _export_bundle(repo, config, target)


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
    takeover_parser = commands.add_parser("takeover")
    takeover_parser.add_argument("--source", choices=sorted(MACHINES), required=True)
    takeover_parser.add_argument("--target", choices=sorted(MACHINES), required=True)
    prepare_parser = commands.add_parser("prepare-export")
    prepare_parser.add_argument("--target", choices=sorted(MACHINES), required=True)
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
        elif args.command == "takeover":
            takeover_from(
                repo,
                config,
                source=args.source,
                target=args.target,
            )
        elif args.command == "prepare-export":
            print(prepare_export(repo, config, target=args.target))
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
