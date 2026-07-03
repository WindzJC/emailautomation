#!/usr/bin/env python3
"""Zero-send Private JC SMTP/IMAP authentication diagnostic."""

from __future__ import annotations

import argparse
import imaplib
import os
import smtplib
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import settings  # Loads the same runtime environment files as the application.
from private_bounce_hygiene import PRIVATE_IMAP_HOST, PRIVATE_IMAP_PORT
from send_shard import PROFILES, SMTP_PRESETS, smtp_close, smtp_login


def _result(label: str, key_name: str, ok: bool, category: str) -> None:
    print(f"{label}: {'SUCCESS' if ok else 'FAILURE'} key={key_name} category={category}")


def run_diagnostic(
    *,
    check_smtp: bool,
    check_imap: bool,
    smtp_login_func: Callable[..., object] = smtp_login,
    imap_factory: Callable[..., object] = imaplib.IMAP4_SSL,
) -> int:
    profile = PROFILES["private_jc"]
    key_name = str(profile["password_env"])
    password = os.environ.get(key_name, "")
    mailbox = str(profile["from_email"])
    print(f"PROFILE: private_jc credential_key={key_name} configured={'yes' if bool(password) else 'no'}")
    if not password:
        if check_smtp:
            _result("SMTP", key_name, False, "credential_missing")
        if check_imap:
            _result("IMAP", key_name, False, "credential_missing")
        return 2

    failed = False
    if check_smtp:
        smtp = None
        try:
            host, port = SMTP_PRESETS["private"]
            smtp = smtp_login_func(host, port, mailbox, password)
            _result("SMTP", key_name, True, "smtp_auth_ok")
        except smtplib.SMTPAuthenticationError:
            failed = True
            _result("SMTP", key_name, False, "smtp_auth_failure")
        except Exception:
            failed = True
            _result("SMTP", key_name, False, "smtp_connection_failure")
        finally:
            smtp_close(smtp)

    if check_imap:
        client = None
        try:
            client = imap_factory(PRIVATE_IMAP_HOST, PRIVATE_IMAP_PORT, timeout=30)
            client.login(mailbox, password)
            _result("IMAP", key_name, True, "imap_auth_ok")
        except imaplib.IMAP4.error:
            failed = True
            _result("IMAP", key_name, False, "imap_auth_failure")
        except Exception:
            failed = True
            _result("IMAP", key_name, False, "imap_connection_failure")
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smtp", action="store_true", help="Authenticate to SMTP without sending.")
    parser.add_argument("--imap", action="store_true", help="Authenticate to IMAP without reading mail.")
    parser.add_argument("--all", action="store_true", help="Run both zero-send authentication checks.")
    args = parser.parse_args()
    check_smtp = bool(args.smtp or args.all)
    check_imap = bool(args.imap or args.all)
    if not check_smtp and not check_imap:
        profile = PROFILES["private_jc"]
        key_name = str(profile["password_env"])
        print(f"PROFILE: private_jc credential_key={key_name} configured={'yes' if bool(os.environ.get(key_name, '')) else 'no'}")
        print("NO NETWORK CHECKS: pass --smtp, --imap, or --all explicitly.")
        return 0
    return run_diagnostic(check_smtp=check_smtp, check_imap=check_imap)


if __name__ == "__main__":
    raise SystemExit(main())
