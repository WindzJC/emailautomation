import argparse
import csv
from pathlib import Path
from email.utils import parseaddr


DEFAULT_MAPPING = [
    # Private
    ("private_marketing_log.csv", "recipients_1.csv"),
    ("private_jordan_kendrick_log.csv", "recipients_2.csv"),
    ("private_jodi_horowitz_log.csv", "recipients_3.csv"),
    ("private_alison_log.csv", "recipients_4.csv"),
    ("private_fiorela_log.csv", "recipients_5.csv"),
    # Gmail
    ("gmail_corporate_log.csv", "recipients_g1.csv"),
    ("gmail_sally_log.csv", "recipients_g2.csv"),
    ("gmail_jordan_log.csv", "recipients_g3.csv"),
    ("gmail_josefina_log.csv", "recipients_g4.csv"),
    # Astra Gmail
    ("astra_astra_log.csv", "recipients_astra1.csv"),
    ("astra_jc_log.csv", "recipients_astra2.csv"),
    ("astra_jordanA_log.csv", "recipients_astra3.csv"),
    ("astra_kentc_log.csv", "recipients_astra4.csv"),
    ("astra_zachking_log.csv", "recipients_astra5.csv"),
    ("astra_alex_log.csv", "recipients_astra6.csv"),
    ("astra_megan_log.csv", "recipients_astra7.csv"),
]


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
    ap.add_argument("--base", default="", help="Base folder containing logs/recipients (default: script folder)")
    ap.add_argument("--show_list", action="store_true", help="Print pending emails per log")
    ap.add_argument("--list_limit", type=int, default=0, help="Limit pending list per log (0 = no limit)")
    ap.add_argument("--unsub_csv", default="unsubscribed.csv")
    ap.add_argument("--suppress_csv", default="suppressed.csv")
    ap.add_argument("--compact", action="store_true", help="Compact output (one line per log)")
    args = ap.parse_args()

    base = Path(args.base) if args.base else Path(__file__).resolve().parent

    unsub = load_emails_from_csv(base / args.unsub_csv)
    supp = load_emails_from_csv(base / args.suppress_csv)

    rows = []
    total_logs = 0
    total_pending = 0

    for log_name, recipients_name in DEFAULT_MAPPING:
        total_logs += 1
        log_path = base / log_name
        csv_path = base / recipients_name

        if not csv_path.exists():
            rows.append({
                "log": log_name,
                "missing": True,
                "recipients": recipients_name,
            })
            continue

        recipients = load_emails_from_csv(csv_path)
        done = load_done_from_log(log_path)
        pending = sorted(recipients - done - unsub - supp)
        total_pending += len(pending)

        rows.append({
            "log": log_name,
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
                print(f"- {r['log']}: missing recipients file {r['recipients']}")
                continue
            print(f"- {r['log']}: pending={r['pending']} / total={r['total']}")
    else:
        log_width = max(len(r["log"]) for r in rows) if rows else 12
        header = (
            f"{'LOG':<{log_width}}  {'PENDING':>7}  {'TOTAL':>7}  "
            f"{'SENT':>7}  {'UNSUB':>7}  {'SUPPR':>7}"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            if r.get("missing"):
                print(f"{r['log']:<{log_width}}  MISSING  {r['recipients']}")
                continue
            print(
                f"{r['log']:<{log_width}}  {r['pending']:>7}  {r['total']:>7}  "
                f"{r['sent_invalid']:>7}  {r['unsub']:>7}  {r['suppressed']:>7}"
            )

    for r in rows:
        pending = r.get("pending_list") or []
        if not pending:
            continue
        if not args.show_list:
            continue
        show = pending if args.list_limit <= 0 else pending[: args.list_limit]
        print(f"\n{r['log']}: pending list")
        for e in show:
            print(f"  {e}")
        if args.list_limit > 0 and len(pending) > args.list_limit:
            print(f"  ...and {len(pending) - args.list_limit} more")

    print(f"\nSUMMARY: total_logs={total_logs} | total_pending={total_pending}")


if __name__ == "__main__":
    main()
