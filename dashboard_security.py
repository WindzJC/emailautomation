from __future__ import annotations

import argparse
import ipaddress
import os
import secrets
from dataclasses import dataclass
from typing import Mapping, Sequence


NO_AUTH_ENV_VARS = ("DASHBOARD_AUTH_DISABLED", "LOCAL_DASHBOARD_NO_AUTH")
PLACEHOLDER_CREDENTIALS = frozenset(
    {
        "admin",
        "change-me",
        "change_me",
        "changeme",
        "default",
        "password",
        "placeholder",
        "replace-me",
        "replace_me",
        "secret",
        "sentinel",
        "your-password-here",
        "your-secret-here",
    }
)


@dataclass(frozen=True)
class DashboardSecurityStatus:
    credentials_valid: bool
    no_auth_requested: bool
    no_auth_allowed: bool
    host_is_loopback: bool
    tunnel_mode: bool
    errors: tuple[str, ...]

    @property
    def startup_allowed(self) -> bool:
        if self.no_auth_requested and not self.no_auth_allowed:
            return False
        return self.credentials_valid or self.no_auth_allowed


def env_flag(name: str, env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def no_auth_requested(env: Mapping[str, str] | None = None) -> bool:
    return any(env_flag(name, env) for name in NO_AUTH_ENV_VARS)


def is_loopback_host(host: str) -> bool:
    value = str(host or "").strip().lower()
    if value == "localhost":
        return True
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def validate_dashboard_security(
    *,
    password: str,
    session_secret: str,
    host: str,
    tunnel_mode: bool = False,
    env: Mapping[str, str] | None = None,
) -> DashboardSecurityStatus:
    clean_password = str(password or "").strip()
    clean_session_secret = str(session_secret or "").strip()
    errors: list[str] = []

    if not clean_password:
        errors.append("missing_password")
    elif clean_password.lower() in PLACEHOLDER_CREDENTIALS:
        errors.append("placeholder_password")

    if not clean_session_secret:
        errors.append("missing_session_secret")
    elif clean_session_secret.lower() in PLACEHOLDER_CREDENTIALS:
        errors.append("placeholder_session_secret")

    if (
        clean_password
        and clean_session_secret
        and secrets.compare_digest(clean_password, clean_session_secret)
    ):
        errors.append("credentials_not_independent")

    requested = no_auth_requested(env)
    loopback = is_loopback_host(host)
    no_auth_allowed = requested and loopback and not tunnel_mode
    if requested and not loopback:
        errors.append("no_auth_requires_loopback")
    if requested and tunnel_mode:
        errors.append("no_auth_forbidden_for_tunnel")

    credential_errors = {
        "missing_password",
        "placeholder_password",
        "missing_session_secret",
        "placeholder_session_secret",
        "credentials_not_independent",
    }
    return DashboardSecurityStatus(
        credentials_valid=not any(error in credential_errors for error in errors),
        no_auth_requested=requested,
        no_auth_allowed=no_auth_allowed,
        host_is_loopback=loopback,
        tunnel_mode=bool(tunnel_mode),
        errors=tuple(errors),
    )


def require_dashboard_startup_security(
    *,
    password: str,
    session_secret: str,
    host: str,
    tunnel_mode: bool = False,
    env: Mapping[str, str] | None = None,
) -> DashboardSecurityStatus:
    status = validate_dashboard_security(
        password=password,
        session_secret=session_secret,
        host=host,
        tunnel_mode=tunnel_mode,
        env=env,
    )
    if status.startup_allowed:
        return status
    reasons = ", ".join(status.errors) or "invalid_dashboard_security_configuration"
    raise RuntimeError(
        "Dashboard startup refused: authentication configuration is invalid "
        f"({reasons}). Configure independent non-placeholder credentials, or use an "
        "explicit no-auth development flag on a loopback-only non-tunnel launch."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate dashboard launch security.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--tunnel", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    require_dashboard_startup_security(
        password=os.environ.get("DASHBOARD_AUTH_PASSWORD", ""),
        session_secret=os.environ.get("DASHBOARD_SESSION_SECRET", ""),
        host=args.host,
        tunnel_mode=bool(args.tunnel),
    )
    print("Dashboard security preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
