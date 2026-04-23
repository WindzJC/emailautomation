from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


SENDGRID_API_KEY_NAME = "SENDGRID_API_KEY"
PLACEHOLDER_SENDGRID_API_KEYS = {
    "",
    "PASTE_WORKING_SENDGRID_KEY_HERE",
    "YOUR_SENDGRID_API_KEY",
    "PASTE_SENDGRID_API_KEY_HERE",
    "REPLACE_ME",
    "CHANGE_ME",
    "CHANGEME",
}


@dataclass(frozen=True)
class SendGridKeyResolution:
    key: str
    source_label: str
    masked_key: str
    warning: str
    error: str

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.key)


def mask_sendgrid_api_key(value: str) -> str:
    key = str(value or "").strip()
    if not key:
        return "(missing)"
    if len(key) <= 12:
        return f"{key[:4]}...{key[-2:]}"
    return f"{key[:6]}...{key[-4:]}"


def is_placeholder_sendgrid_api_key(value: str) -> bool:
    key = str(value or "").strip()
    if not key:
        return True
    normalized = key.upper()
    if normalized in PLACEHOLDER_SENDGRID_API_KEYS:
        return True
    if "PLACEHOLDER" in normalized:
        return True
    if "SENDGRID" in normalized and "KEY" in normalized and not key.startswith("SG."):
        return True
    if normalized.startswith("PASTE_") and not key.startswith("SG."):
        return True
    return False


def looks_like_sendgrid_api_key(value: str) -> bool:
    key = str(value or "").strip()
    if not key.startswith("SG."):
        return False
    parts = key.split(".")
    return len(parts) >= 3 and all(parts[:3])


def _unquote_env_value(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _read_env_value(path: Path, name: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=\s*(.+?)\s*$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(raw_line)
        if not match:
            continue
        return _unquote_env_value(match.group(1))
    return ""


def _candidate_error(value: str, source_label: str) -> str:
    if not str(value or "").strip():
        return ""
    if is_placeholder_sendgrid_api_key(value):
        return (
            f"{SENDGRID_API_KEY_NAME} from {source_label} is a placeholder or blank value. "
            f"Update {source_label} with the real SendGrid key or clear the inherited environment override."
        )
    return ""


def resolve_sendgrid_api_key(
    *,
    env: Mapping[str, str] | None = None,
    env_files: Sequence[str | Path] | None = None,
) -> SendGridKeyResolution:
    active_env = os.environ if env is None else env
    checked_sources: list[str] = []

    for raw_path in env_files or ():
        path = Path(raw_path)
        checked_sources.append(path.name or str(path))
        if not path.exists():
            continue
        value = _read_env_value(path, SENDGRID_API_KEY_NAME)
        if not value:
            continue
        error = _candidate_error(value, path.name)
        if error:
            return SendGridKeyResolution(
                key="",
                source_label=path.name,
                masked_key="(invalid)",
                warning="",
                error=error,
            )
        warning = ""
        if not looks_like_sendgrid_api_key(value):
            warning = (
                f"{SENDGRID_API_KEY_NAME} from {path.name} does not match the usual SendGrid SG.* format. "
                "Verify the key before sending."
            )
        return SendGridKeyResolution(
            key=value,
            source_label=path.name,
            masked_key=mask_sendgrid_api_key(value),
            warning=warning,
            error="",
        )

    inherited = str(active_env.get(SENDGRID_API_KEY_NAME, "") or "").strip()
    checked_sources.append("inherited environment")
    if inherited:
        error = _candidate_error(inherited, "the inherited environment")
        if error:
            return SendGridKeyResolution(
                key="",
                source_label="inherited environment",
                masked_key="(invalid)",
                warning="",
                error=error,
            )
        warning = ""
        if not looks_like_sendgrid_api_key(inherited):
            warning = (
                f"{SENDGRID_API_KEY_NAME} from the inherited environment does not match the usual SendGrid SG.* format. "
                "Verify the key before sending."
            )
        return SendGridKeyResolution(
            key=inherited,
            source_label="inherited environment",
            masked_key=mask_sendgrid_api_key(inherited),
            warning=warning,
            error="",
        )

    checked = ", ".join(dict.fromkeys(source for source in checked_sources if source))
    return SendGridKeyResolution(
        key="",
        source_label="",
        masked_key="(missing)",
        warning="",
        error=f"{SENDGRID_API_KEY_NAME} was not found. Expected it in {checked or '.env.local, .env'}.",
    )
