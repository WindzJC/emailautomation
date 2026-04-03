import argparse
import csv
from email.utils import parseaddr
from pathlib import Path

import settings
from send_shard import PROFILES


def current_mapping() -> list[tuple[str, Path, Path]]:
    rows: list[tuple[str, Path, Path]] = []
    for profile_name, cfg in sorted(PROFILES.items()):
        provider = str(cfg.get("provider") or "").strip().lower()
        if provider not in {"private", "sendgrid"}:
            continue
        csv_name = str(cfg.get("csv") or "").strip()
        log_name = str(cfg.get("log") or "").strip()
        if not csv_name or not log_name:
            continue
        rows.append(
            (
                profile_name,
                settings.log_path(log_name),
                settings.shard_path(csv_name),
            )
        )
    return rows


def norm_email(s: str) -> str:
    _, addr = parseaddr(s or "")
    return addr.strip().lower()


def load_emails_from_csv(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def load_done_from_log(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = (r.get("Status") or "").strip().upper()
            if st not in ("SENT", "INVALID"):
                continue
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show_list", action="store_true", help="Print pending emails per log")
    ap.add_argument("--list_limit", type=int, default=0, help="Limit pending list per log (0 = no limit)")
    ap.add_argument("--unsub_csv", default=str(settings.UNSUBSCRIBED_PATH))
    ap.add_argument("--suppress_csv", default=str(settings.SUPPRESSED_PATH))
    ap.add_argument("--compact", action="store_true", help="Compact output (one line per log)")
    args = ap.parse_args()

    unsub = load_emails_from_csv(Path(args.unsub_csv))
    supp = load_emails_from_csv(Path(args.suppress_csv))
    mapping = current_mapping()

    rows = []
    total_logs = 0
    total_pending = 0

    for profile_name, log_path, csv_path in mapping:
        total_logs += 1
        if not csv_path.exists():
            rows.append({
                "profile": profile_name,
                "missing": True,
                "recipients": str(csv_path),
            })
            continue

        recipients = load_emails_from_csv(csv_path)
        done = load_done_from_log(log_path)
        pending = sorted(recipients - done - unsub - supp)
        total_pending += len(pending)

        rows.append({
            "profile": profile_name,
            "missing": False,
            "pending": len(pending),
            "total": len(recipients),
            "sent_invalid": len(recipients & done),
            "unsub": len(recipients & unsub),
            "suppressed": len(recipients & supp),
            "pending_list": pending,
        })

    if args.compact:
        for r in rows:
            if r.get("missing"):
                print(f"- {r['profile']}: missing recipients file {r['recipients']}")
                continue
            print(f"- {r['profile']}: pending={r['pending']} / total={r['total']}")
    else:
        log_width = max(len(r["profile"]) for r in rows) if rows else 12
        header = (
            f"{'PROFILE':<{log_width}}  {'PENDING':>7}  {'TOTAL':>7}  "
            f"{'SENT':>7}  {'UNSUB':>7}  {'SUPPR':>7}"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            if r.get("missing"):
                print(f"{r['profile']:<{log_width}}  MISSING  {r['recipients']}")
                continue
            print(
                f"{r['profile']:<{log_width}}  {r['pending']:>7}  {r['total']:>7}  "
                f"{r['sent_invalid']:>7}  {r['unsub']:>7}  {r['suppressed']:>7}"
            )

    for r in rows:
        pending = r.get("pending_list") or []
        if not pending:
            continue
        if not args.show_list:
            continue
        show = pending if args.list_limit <= 0 else pending[: args.list_limit]
        print(f"\n{r['profile']}: pending list")
        for e in show:
            print(f"  {e}")
        if args.list_limit > 0 and len(pending) > args.list_limit:
            print(f"  ...and {len(pending) - args.list_limit} more")

    print(f"\nSUMMARY: total_logs={total_logs} | total_pending={total_pending}")


if __name__ == "__main__":
    main()
