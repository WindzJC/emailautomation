import csv, argparse
from pathlib import Path
from datetime import datetime, timezone

from email_validator import validate_email, EmailNotValidError
import dns.resolver

ROLE_PREFIXES = {"admin","support","info","sales","billing","contact","help","abuse","postmaster","noreply","no-reply"}
# optional: put disposable domains (one per line) in disposable_domains.txt
DISPOSABLE_FILE = Path("disposable_domains.txt")

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def load_disposable():
    if not DISPOSABLE_FILE.exists():
        return set()
    return {line.strip().lower() for line in DISPOSABLE_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}

def has_null_mx(mx_answers):
    # RFC 7505 “null MX”: preference 0, exchange "."
    for r in mx_answers:
        try:
            if int(r.preference) == 0 and str(r.exchange).rstrip(".") == "":
                return True
        except Exception:
            pass
    return False

def precheck(addr: str, disposable_domains: set, mx_cache: dict) -> tuple[bool, str]:
    addr = (addr or "").strip()
    if not addr:
        return False, "empty"

    try:
        v = validate_email(addr, check_deliverability=False)
        email = v.email
        domain = v.domain.lower()
    except EmailNotValidError as e:
        return False, f"bad_syntax: {e}"

    local = email.split("@", 1)[0].lower()
    if local in ROLE_PREFIXES:
        return False, "role_account"

    if domain in disposable_domains:
        return False, "disposable_domain"

    if domain in mx_cache:
        mx_ok, reason = mx_cache[domain]
        return mx_ok, reason

    try:
        answers = dns.resolver.resolve(domain, "MX")
        if has_null_mx(answers):
            mx_cache[domain] = (False, "null_mx")
            return False, "null_mx"
        mx_cache[domain] = (True, "ok")
        return True, "ok"
    except Exception as e:
        mx_cache[domain] = (False, f"no_mx_or_dns_fail")
        return False, f"no_mx_or_dns_fail"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--suppressed", default="suppressed.csv")
    ap.add_argument("--email_col", default="Email")
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.out)
    supp = Path(args.suppressed)

    disposable = load_disposable()
    mx_cache = {}
    seen = set()

    with inp.open(newline="", encoding="utf-8-sig") as f,\
         outp.open("w", newline="", encoding="utf-8") as fo,\
         supp.open("w", newline="", encoding="utf-8") as fs:

        r = csv.DictReader(f)
        w_ok = csv.DictWriter(fo, fieldnames=r.fieldnames)
        w_bad = csv.DictWriter(fs, fieldnames=["TimestampUTC","Email","Reason"])
        w_ok.writeheader()
        w_bad.writeheader()

        for row in r:
            email = (row.get(args.email_col) or "").strip().lower()
            if not email:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": "", "Reason": "missing_email"})
                continue
            if email in seen:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": "duplicate"})
                continue
            seen.add(email)

            ok, reason = precheck(email, disposable, mx_cache)
            if ok:
                w_ok.writerow(row)
            else:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": reason})

if __name__ == "__main__":
    main()
