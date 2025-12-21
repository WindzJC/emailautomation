import argparse
import csv
import glob
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parseaddr
from typing import Optional


def norm_email(s: str) -> str:
    _, addr = parseaddr(s or "")
    return addr.strip().lower()


def parse_ts(ts: str) -> Optional[datetime]:
    ts = (ts or "").strip()
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def fmt(dt: Optional[datetime]) -> str:
    if not dt:
        return "n/a"
    manila = dt + timedelta(hours=8)
    return f"{dt.isoformat()}Z | Manila: {manila.strftime('%Y-%m-%d %H:%M:%S')}"


def remaining_str(resume_dt: Optional[datetime]) -> str:
    if not resume_dt:
        return "n/a"
    now = datetime.now(timezone.utc)
    sec = int((resume_dt - now).total_seconds())
    if sec <= 0:
        return "now"
    h, rem = divmod(sec, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m}m"


def looks_hard_limited(last_error: str) -> bool:
    le = (last_error or "").lower()
    return (
        "5.4.5" in le
        or "daily user sending limit exceeded" in le
        or "too many unique external recipients" in le
        or "has exceeded the gmail sending limit" in le
        or "sending limit exceeded" in le
    )


def looks_auth_failed(last_error: str) -> bool:
    le = (last_error or "").lower()
    return (
        "auth_failed" in le
        or "badcredentials" in le
        or "username and password not accepted" in le
        or " 535" in le
        or le.startswith("535")
    )


def is_private_log(filename: str) -> bool:
    n = Path(filename).name.lower()
    return n == "private_domain_log.csv" or n.startswith("private_") or "private" in n


def rolling_24h_stats(log_path: Path, my_domains: set[str], now: datetime) -> dict:
    cutoff = now - timedelta(hours=24)

    messages = 0
    sent_times = []  # timestamps of SENT within 24h
    ext_last = {}    # external_email -> latest timestamp within 24h
    last_error = ""

    if not log_path.exists():
        return {
            "log": str(log_path),
            "messages": 0,
            "unique_external": 0,
            "resume_messages": None,
            "resume_unique_external": None,
            "last_error": "",
        }

    with log_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # latest ERROR line
    for r in reversed(rows[-800:]):
        if (r.get("Status") or "").strip().upper() == "ERROR":
            last_error = (r.get("Info") or "").strip()
            break

    for r in rows:
        if (r.get("Status") or "").strip().upper() != "SENT":
            continue

        t = parse_ts(r.get("TimestampUTC") or "")
        if not t or t < cutoff:
            continue

        messages += 1
        sent_times.append(t)

        email_addr = norm_email(r.get("Email") or "")
        if "@" in email_addr:
            domain = email_addr.split("@", 1)[1]
            if domain not in my_domains:
                prev = ext_last.get(email_addr)
                if prev is None or t > prev:
                    ext_last[email_addr] = t

    sent_times.sort()
    resume_messages = (sent_times[0] + timedelta(hours=24)) if sent_times else None
    resume_unique_external = (min(ext_last.values()) + timedelta(hours=24)) if ext_last else None

    return {
        "log": str(log_path),
        "messages": messages,
        "unique_external": len(ext_last),
        "resume_messages": resume_messages,
        "resume_unique_external": resume_unique_external,
        "last_error": last_error,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--my_domains", required=True, help="comma-separated internal domains")
    ap.add_argument("--log", help="single Gmail sender log file (e.g., corporate_log.csv)")
    ap.add_argument("--pattern", default="*_log.csv", help="glob pattern for logs (default: *_log.csv)")
    ap.add_argument("--max_messages_24h", type=int, default=450)
    ap.add_argument("--max_unique_external_24h", type=int, default=450)
    args = ap.parse_args()

    my_domains = {d.strip().lower() for d in args.my_domains.split(",") if d.strip()}

    # Gmail-only logs (exclude private_* and private_domain_log.csv)
    if args.log:
        if is_private_log(args.log):
            print("ERROR: --log points to a PrivateEmail log. Use a Gmail sender log like corporate_log.csv.")
            return
        logs = [args.log]
    else:
        logs = [p for p in sorted(glob.glob(args.pattern)) if not is_private_log(p)]

    if not logs:
        print(f"No Gmail logs found for pattern: {args.pattern}")
        return

    now = datetime.now(timezone.utc)

    print("GMAIL LAST 24H (per sender log):")
    print(f"limits: messages_24h={args.max_messages_24h} | unique_external_24h={args.max_unique_external_24h}")
    print()

    results = []
    for lp in logs:
        r = rolling_24h_stats(Path(lp), my_domains, now)

        status = "OK"
        if looks_auth_failed(r["last_error"]):
            status = "AUTH FAILED"
        elif looks_hard_limited(r["last_error"]):
            status = "HARD LIMITED (GMAIL)"
        elif r["messages"] >= args.max_messages_24h:
            status = "NEAR/AT MSG LIMIT"
        elif r["unique_external"] >= args.max_unique_external_24h:
            status = "NEAR/AT UNIQUE-EXT LIMIT"

        results.append((Path(r["log"]).name, r, status))

    issues = [(n, r, s) for (n, r, s) in results if s != "OK"]
    oks = [(n, r, s) for (n, r, s) in results if s == "OK"]

    print("ISSUES:")
    if not issues:
        print("- none")
    else:
        for name, r, status in issues:
            print(f"- {name}: sent={r['messages']} | unique_ext={r['unique_external']} | {status}")

            if status == "HARD LIMITED (GMAIL)":
                print(f"  resume(messages): {fmt(r['resume_messages'])} | remaining: {remaining_str(r['resume_messages'])}")
                print(f"  resume(unique-ext): {fmt(r['resume_unique_external'])} | remaining: {remaining_str(r['resume_unique_external'])}")

            if status == "NEAR/AT MSG LIMIT":
                print(f"  resume(messages): {fmt(r['resume_messages'])} | remaining: {remaining_str(r['resume_messages'])}")

            if status == "NEAR/AT UNIQUE-EXT LIMIT":
                print(f"  resume(unique-ext): {fmt(r['resume_unique_external'])} | remaining: {remaining_str(r['resume_unique_external'])}")

            if r["last_error"]:
                print(f"  last_error: {r['last_error'][:180]}")

    print("\nOK:")
    if not oks:
        print("- none")
    else:
        for name, r, _ in oks:
            print(f"- {name}: sent={r['messages']} | unique_ext={r['unique_external']} | OK")

    print(f"\nSUMMARY: ok={len(oks)} | issues={len(issues)} | total={len(results)}")


if __name__ == "__main__":
    main()
