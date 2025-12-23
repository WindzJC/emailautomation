import csv, argparse
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    from email_validator import validate_email, EmailNotValidError
except Exception:
    validate_email = None
    EmailNotValidError = Exception

try:
    import dns.resolver
except Exception:
    dns = None

ROLE_PREFIXES = {"admin","support","info","sales","billing","contact","help","abuse","postmaster","noreply","no-reply"}
# optional: put disposable domains (one per line) in disposable_domains.txt
DISPOSABLE_FILE = Path("disposable_domains.txt")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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

def precheck(addr: str, disposable_domains: set, mx_cache: dict, skip_mx: bool) -> tuple[bool, str]:
    addr = (addr or "").strip()
    if not addr:
        return False, "empty"

    if validate_email:
        try:
            v = validate_email(addr, check_deliverability=False)
            email = v.email
            domain = v.domain.lower()
        except EmailNotValidError as e:
            return False, f"bad_syntax: {e}"
    else:
        email = addr.strip().lower()
        if not EMAIL_RE.match(email):
            return False, "bad_syntax"
        domain = email.split("@", 1)[1].lower()

    local = email.split("@", 1)[0].lower()
    if local in ROLE_PREFIXES:
        return False, "role_account"

    if domain in disposable_domains:
        return False, "disposable_domain"

    if skip_mx or dns is None:
        return True, "ok"

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
    except Exception:
        mx_cache[domain] = (False, "no_mx_or_dns_fail")
        return False, "no_mx_or_dns_fail"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--suppressed", default="suppressed.csv")
    ap.add_argument("--email_col", default="Email")
    ap.add_argument("--no_mx", action="store_true")
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.out)
    supp = Path(args.suppressed)

    disposable = load_disposable()
    mx_cache = {}
    seen = set()

    if validate_email is None:
        print("WARN: email_validator not installed; using basic syntax check.")
    if dns is None and not args.no_mx:
        print("WARN: dnspython not installed; skipping MX check.")

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

            ok, reason = precheck(email, disposable, mx_cache, args.no_mx)
            if ok:
                w_ok.writerow(row)
            else:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": reason})

if __name__ == "__main__":
    main()
