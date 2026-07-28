"""Fail-closed runtime authority shared by senders and handoff tooling."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MACHINES = {"mac", "windows-wsl"}
ACTIVE_STATUS = "active"
AUTHORITY_FILENAME = "runtime_authority.json"
GENERATION_FLOOR_RELATIVE = Path(".runtime_handoff/generation_floor.json")
REQUIRED_FIELDS = {
    "authorized_machine",
    "generation",
    "bundle_id",
    "source_machine",
    "target_machine",
    "created_utc",
    "expected_git_commit",
    "runtime_manifest_hash",
    "status",
}


class AuthorityError(RuntimeError):
    """Authority is absent, malformed, stale, or assigned elsewhere."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_machine(env: dict[str, str] | None = None) -> str:
    values = os.environ if env is None else env
    override = str(values.get("ASTRA_MACHINE_ID", "")).strip().lower()
    if override:
        if override not in MACHINES:
            raise AuthorityError(
                f"ASTRA_MACHINE_ID must be one of {sorted(MACHINES)}, got {override!r}"
            )
        return override
    if platform.system() == "Darwin":
        return "mac"
    if platform.system() == "Linux":
        try:
            release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8")
            version = Path("/proc/version").read_text(encoding="utf-8")
        except OSError:
            release = platform.release()
            version = platform.version()
        if "microsoft" in f"{release} {version}".lower():
            return "windows-wsl"
    raise AuthorityError(
        "Machine identity could not be inferred; set ASTRA_MACHINE_ID=mac or windows-wsl"
    )


def authority_path(repo: Path) -> Path:
    return repo / "data/state" / AUTHORITY_FILENAME


def generation_floor_path(repo: Path) -> Path:
    return repo / GENERATION_FLOOR_RELATIVE


def _atomic_json_write(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def load_authority(repo: Path) -> dict[str, Any]:
    path = authority_path(repo)
    if not path.is_file():
        raise AuthorityError(f"Authority file is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AuthorityError(f"Authority file is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise AuthorityError("Authority file must contain a JSON object")
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        raise AuthorityError("Authority file is missing fields: " + ", ".join(missing))
    generation = payload.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise AuthorityError("Authority generation must be an integer >= 1")
    for field in ("authorized_machine", "source_machine", "target_machine"):
        if payload.get(field) not in MACHINES:
            raise AuthorityError(f"Invalid authority {field}: {payload.get(field)!r}")
    for field in (
        "bundle_id",
        "created_utc",
        "expected_git_commit",
        "runtime_manifest_hash",
        "status",
    ):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise AuthorityError(f"Authority field {field} must be a non-empty string")
    return payload


def load_generation_floor(repo: Path) -> int:
    path = generation_floor_path(repo)
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload["generation"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AuthorityError(f"Generation floor is unreadable: {path}") from exc
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AuthorityError("Generation floor must be an integer >= 1")
    return value


def write_generation_floor(repo: Path, generation: int, bundle_id: str) -> None:
    current = load_generation_floor(repo)
    if generation < current:
        raise AuthorityError(
            f"Refusing generation rollback from local floor {current} to {generation}"
        )
    _atomic_json_write(
        generation_floor_path(repo),
        {
            "generation": generation,
            "bundle_id": bundle_id,
            "updated_utc": utc_now(),
        },
    )


def write_authority(repo: Path, payload: dict[str, Any]) -> None:
    # Validate through an isolated representation before replacing live state.
    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise AuthorityError("Authority payload is incomplete")
    generation = payload.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise AuthorityError("Authority generation must be an integer >= 1")
    _atomic_json_write(authority_path(repo), payload)


def assert_send_authorized(
    repo: Path,
    *,
    machine: str | None = None,
) -> dict[str, Any]:
    identity = machine or current_machine()
    authority = load_authority(repo)
    if authority["status"] != ACTIVE_STATUS:
        raise AuthorityError(
            f"Runtime authority is {authority['status']!r}; real sending is disabled"
        )
    if authority["authorized_machine"] != identity:
        raise AuthorityError(
            f"Runtime is authorized for {authority['authorized_machine']}, not {identity}"
        )
    floor = load_generation_floor(repo)
    if floor < 1:
        raise AuthorityError("Local generation floor is missing; activation is required")
    if authority["generation"] != floor:
        raise AuthorityError(
            f"Authority generation {authority['generation']} does not match local floor {floor}"
        )
    if authority["source_machine"] == authority["target_machine"]:
        raise AuthorityError("Authority source and target machines must differ")
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise AuthorityError("Current Git commit could not be determined")
    head = result.stdout.strip()
    if authority["expected_git_commit"] != head:
        raise AuthorityError(
            "Authority expected Git commit does not match the current checkout"
        )
    return authority
