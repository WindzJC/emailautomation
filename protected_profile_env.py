from __future__ import annotations

import grp
import os
import re
import stat
from pathlib import Path
from typing import Mapping


DEFAULT_PROFILE_ENV_DIR = Path("/etc/astra-emailautomation/profiles")
_PROFILE_NAME_RE = re.compile(r"[a-z0-9_]+")


class ProtectedProfileEnvError(RuntimeError):
    """Secret-free failure raised while reading a protected profile env file."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _cloud_permissions_required() -> bool:
    return os.environ.get("ASTRA_MACHINE_ID", "").strip().lower() == "cloud"


def _require_cloud_metadata(metadata: os.stat_result, *, directory: bool) -> None:
    try:
        astra_gid = grp.getgrnam("astra").gr_gid
    except KeyError as exc:
        raise ProtectedProfileEnvError(
            "credential_file_unsafe",
            "The astra credential group is unavailable.",
        ) from exc

    expected_mode = 0o750 if directory else 0o640
    if (
        metadata.st_uid != 0
        or metadata.st_gid != astra_gid
        or stat.S_IMODE(metadata.st_mode) != expected_mode
    ):
        raise ProtectedProfileEnvError(
            "credential_file_unsafe",
            "Protected profile credential permissions are unsafe.",
        )


def read_protected_profile_env(
    profile: str,
    profile_env_dir: Path = DEFAULT_PROFILE_ENV_DIR,
) -> tuple[dict[str, str], str]:
    """Read one profile env through a pinned, non-symlink directory descriptor."""

    profile_name = str(profile or "").strip()
    if not _PROFILE_NAME_RE.fullmatch(profile_name):
        raise ProtectedProfileEnvError(
            "credential_identity_mismatch",
            "Protected profile credential identity is invalid.",
        )

    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory_flag is None:
        raise ProtectedProfileEnvError(
            "credential_file_unsafe",
            "Credential verification requires secure no-follow support.",
        )

    directory = Path(profile_env_dir)
    try:
        before_directory = directory.lstat()
        if stat.S_ISLNK(before_directory.st_mode) or not stat.S_ISDIR(
            before_directory.st_mode
        ):
            raise ProtectedProfileEnvError(
                "credential_file_unsafe",
                "Protected profile credential directory is unsafe.",
            )
        directory_fd = os.open(directory, os.O_RDONLY | nofollow | directory_flag)
    except ProtectedProfileEnvError:
        raise
    except OSError as exc:
        raise ProtectedProfileEnvError(
            "credential_unavailable",
            "Protected profile credential directory is unavailable.",
        ) from exc

    filename = f"{profile_name}.env"
    try:
        opened_directory = os.fstat(directory_fd)
        if (
            before_directory.st_dev,
            before_directory.st_ino,
        ) != (
            opened_directory.st_dev,
            opened_directory.st_ino,
        ):
            raise ProtectedProfileEnvError(
                "credential_file_unsafe",
                "Protected profile credential directory changed while opening.",
            )
        if _cloud_permissions_required():
            _require_cloud_metadata(opened_directory, directory=True)

        try:
            before_file = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(before_file.st_mode) or not stat.S_ISREG(before_file.st_mode):
                raise ProtectedProfileEnvError(
                    "credential_file_unsafe",
                    f"{profile_name} credential file is unsafe.",
                )
            file_fd = os.open(filename, os.O_RDONLY | nofollow, dir_fd=directory_fd)
        except ProtectedProfileEnvError:
            raise
        except OSError as exc:
            raise ProtectedProfileEnvError(
                "credential_unavailable",
                f"{profile_name} credential file is unavailable.",
            ) from exc

        try:
            opened_file = os.fstat(file_fd)
            if (
                before_file.st_dev,
                before_file.st_ino,
            ) != (
                opened_file.st_dev,
                opened_file.st_ino,
            ) or not stat.S_ISREG(opened_file.st_mode):
                raise ProtectedProfileEnvError(
                    "credential_file_unsafe",
                    "Protected profile credential changed while opening.",
                )
            if _cloud_permissions_required():
                _require_cloud_metadata(opened_file, directory=False)

            chunks: list[bytes] = []
            while True:
                chunk = os.read(file_fd, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)

    try:
        lines = b"".join(chunks).decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ProtectedProfileEnvError(
            "credential_file_unsafe",
            "Protected profile credential file is not valid UTF-8.",
        ) from exc

    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        name, value = raw_line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value

    return values, filename


def resolve_protected_profile_credential(
    profile: str,
    configured_key: str,
    expected_key: str,
    *,
    profile_env_dir: Path = DEFAULT_PROFILE_ENV_DIR,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve a configured secret without exporting, caching, or logging it."""

    key = str(configured_key or "").strip()
    if key != expected_key:
        raise ProtectedProfileEnvError(
            "credential_identity_mismatch",
            "Protected profile credential mapping is invalid.",
        )

    values, source = read_protected_profile_env(profile, profile_env_dir)
    fallback = os.environ if environment is None else environment
    secret = str(values.get(key) or "").strip() or str(fallback.get(key) or "").strip()
    if not secret:
        raise ProtectedProfileEnvError(
            "credential_invalid",
            "Protected profile credential is missing or invalid.",
        )
    return secret, source
