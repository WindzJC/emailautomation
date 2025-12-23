import argparse
import csv
import glob
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List


def parse_ts(ts: str) -> Optional[datetime]:
    ts = (ts or "").strip()
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def fmt_utc_and_manila(dt: Optional[datetime]) -> str:
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


def single_line(s: str) -> str:
    return " ".join((s or "").split())


def last_1h_times(log_path: Path, now: datetime) -> List[datetime]:
    cutoff = now - timedelta(hours=1)
    times: List[datetime] = []
    if not log_path.exists():
        return times

    with log_path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("Status") or "").strip().upper() != "SENT":
                continue
            t = parse_ts(r.get("TimestampUTC") or "")
            if t and t >= cutoff:
                times.append(t)

    times.sort()
    return times


def last_error(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    try:
        with log_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        for r in reversed(rows[-800:]):
            if (r.get("Status") or "").strip().upper() == "ERROR":
                return ((r.get("Info") or "").strip())[:220]
    except Exception:
        return ""
    return ""


def status_for(used: int, cap: int) -> str:
    return "AT/NEAR PER-HOUR CAP" if used >= cap else "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max_messages_1h", type=int, default=50, help="PrivateEmail trial: 50/hour. Paid plans are higher.")
    ap.add_argument("--domain_log", help="Shared domain log (recommended for PrivateEmail domain-wide cap).")
    ap.add_argument("--log", help="Single sender log (optional).")
    ap.add_argument("--pattern", default="private_*_log.csv", help="Glob for PRIVATE sender logs (default: private_*_log.csv)")
    ap.add_argument("--compact", action="store_true", help="Force compact output")
    ap.add_argument("--verbose", action="store_true", help="Show detailed output")
    ap.add_argument("--short", action="store_true", help="One-line table output")
    ap.add_argument("--show_ok", action="store_true", help="Include OK rows in --short output")

    args = ap.parse_args()
    now = datetime.now(timezone.utc)

    if args.short:
        rows: List[tuple[str, int, str, Optional[datetime]]] = []
        if args.domain_log:
            dlog = Path(args.domain_log)
            times = last_1h_times(dlog, now)
            used = len(times)
            st = status_for(used, args.max_messages_1h)
            resume = (times[0] + timedelta(hours=1)) if times else None
            rows.append((dlog.name, used, st, resume))

        logs: List[str]
        if args.log:
            logs = [args.log]
        else:
            logs = sorted(glob.glob(args.pattern))

        if args.domain_log:
            dpath = Path(args.domain_log).resolve()
            logs = [p for p in logs if Path(p).resolve() != dpath]

        for lp in logs:
            p = Path(lp)
            times = last_1h_times(p, now)
            used = len(times)
            st = status_for(used, args.max_messages_1h)
            resume = (times[0] + timedelta(hours=1)) if times else None
            rows.append((p.name, used, st, resume))

        issues = [r for r in rows if r[2] != "OK"]
        show_rows = rows if args.show_ok else issues

        name_w = max((len(r[0]) for r in show_rows), default=8)
        header = f"{'LOG':<{name_w}}  {'SENT':>6}  {'STATUS':<22}  {'RESUME_IN':<10}"
        print(header)
        print("-" * len(header))
        for name, used, st, resume in show_rows:
            resume_in = remaining_str(resume) if resume else "n/a"
            print(f"{name:<{name_w}}  {used:>6}  {st:<22}  {resume_in:<10}")

        summary = f"SUMMARY: ok={len(rows) - len(issues)} | issues={len(issues)} | total={len(rows)}"
        print(summary)
        return

    compact = args.compact or not args.verbose

    if not compact:
        print("PRIVATEEMAIL LAST 1H:")
        print(f"limit: messages_1h={args.max_messages_1h}")
        print()

    # DOMAIN
    if args.domain_log:
        dlog = Path(args.domain_log)
        times = last_1h_times(dlog, now)
        used = len(times)
        st = status_for(used, args.max_messages_1h)
        resume = (times[0] + timedelta(hours=1)) if times else None

        if compact:
            print(f"DOMAIN: {dlog.name}: sent={used} / {args.max_messages_1h} | {st}")
            if st != "OK" and resume:
                print(f"  resume: {fmt_utc_and_manila(resume)} | remaining: {remaining_str(resume)}")
            le = last_error(dlog)
            if st != "OK" and le:
                print(f"  last_error: {single_line(le)}")
        else:
            print("DOMAIN:")
            print(f"- {dlog.name}: sent={used} / {args.max_messages_1h} | {st}")
            if st != "OK" and resume:
                print(f"  resume: {fmt_utc_and_manila(resume)} | remaining: {remaining_str(resume)}")
            le = last_error(dlog)
            if le:
                print(f"  last_error: {single_line(le)}")
            print()

    # SENDER LOGS (private_* only by default)
    logs: List[str]
    if args.log:
        logs = [args.log]
    else:
        logs = sorted(glob.glob(args.pattern))

    # Avoid repeating domain log as a sender entry
    if args.domain_log:
        dpath = Path(args.domain_log).resolve()
        logs = [p for p in logs if Path(p).resolve() != dpath]

    # Build results, then print as ISSUES + OK
    results = []
    for lp in logs:
        p = Path(lp)
        times = last_1h_times(p, now)
        used = len(times)
        st = status_for(used, args.max_messages_1h)
        resume = (times[0] + timedelta(hours=1)) if times else None
        le = last_error(p)
        results.append((p.name, used, st, resume, le))

    issues = [x for x in results if x[2] != "OK"]
    oks = [x for x in results if x[2] == "OK"]

    print("ISSUES:")
    if not issues:
        print("- none")
    else:
        for name, used, st, resume, le in issues:
            print(f"- {name}: sent={used} / {args.max_messages_1h} | {st}")
            if resume and not compact:
                print(f"  resume: {fmt_utc_and_manila(resume)} | remaining: {remaining_str(resume)}")
            if le and not compact:
                print(f"  last_error: {single_line(le)}")

    if not compact:
        print("\nOK:")
        if not oks:
            print("- none")
        else:
            for name, used, _, __, ___ in oks:
                print(f"- {name}: sent={used} / {args.max_messages_1h} | OK")

    total = len(results) + (1 if args.domain_log else 0)
    ok_count = len(oks) + (1 if args.domain_log and status_for(len(last_1h_times(Path(args.domain_log), now)), args.max_messages_1h) == "OK" else 0)
    issue_count = total - ok_count
    summary = f"SUMMARY: ok={ok_count} | issues={issue_count} | total={total}"
    print(summary if compact else f"\n{summary}")


if __name__ == "__main__":
    main()
