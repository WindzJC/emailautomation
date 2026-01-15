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
EMAIL_IN_TEXT_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
COMMON_DOMAIN_FIXES = {
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "hotnail.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "outllok.com": "outlook.com",
    "outlok.com": "outlook.com",
    "yahho.com": "yahoo.com",
    "yaho.com": "yahoo.com",
    "yhoo.com": "yahoo.com",
}

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

def extract_email(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    match = EMAIL_IN_TEXT_RE.search(value)
    return (match.group(0) if match else value).strip()


def is_role_account(local: str) -> bool:
    for prefix in ROLE_PREFIXES:
        if local == prefix:
            return True
        if local.startswith(prefix) and len(local) > len(prefix):
            sep = local[len(prefix)]
            if sep in {".", "-", "_", "+"}:
                return True
    return False


def precheck(
    addr: str,
    disposable_domains: set,
    mx_cache: dict,
    skip_mx: bool,
    allow_role: bool,
    resolver,
) -> tuple[bool, str]:
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
    if not allow_role and is_role_account(local):
        return False, "role_account"

    if domain in disposable_domains:
        return False, "disposable_domain"

    if domain in COMMON_DOMAIN_FIXES:
        fixed_domain = COMMON_DOMAIN_FIXES[domain]
        email = f"{local}@{fixed_domain}"
        domain = fixed_domain

    if skip_mx or dns is None or resolver is None:
        return True, "ok"

    if domain in mx_cache:
        mx_ok, reason = mx_cache[domain]
        return mx_ok, reason

    try:
        answers = resolver.resolve(domain, "MX")
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
    ap.add_argument("--author_col", default="AuthorName")
    ap.add_argument("--title_col", default="BookTitle")
    ap.add_argument("--no_mx", action="store_true")
    ap.add_argument("--allow_role", action="store_true", help="Allow role-based addresses (info@, support@, etc.).")
    ap.add_argument("--mx_timeout", type=float, default=2.0, help="DNS timeout per try (seconds).")
    ap.add_argument("--mx_lifetime", type=float, default=4.0, help="DNS total lifetime (seconds).")
    ap.add_argument(
        "--require_fields",
        action="store_true",
        help="Reject rows missing AuthorName or BookTitle.",
    )
    ap.add_argument(
        "--overwrite_in",
        dest="overwrite_in",
        action="store_true",
        default=False,
        help="Overwrite the input file with the cleaned output.",
    )
    ap.add_argument(
        "--no_overwrite_in",
        dest="overwrite_in",
        action="store_false",
        help="Do not overwrite the input file.",
    )
    ap.add_argument(
        "--drain_in",
        dest="drain_in",
        action="store_true",
        default=True,
        help="Clear the input file after processing (leave header only).",
    )
    ap.add_argument(
        "--no_drain_in",
        dest="drain_in",
        action="store_false",
        help="Do not clear the input file after processing.",
    )
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
    resolver = None
    if dns is not None and not args.no_mx:
        resolver = dns.resolver.Resolver()
        resolver.timeout = float(args.mx_timeout)
        resolver.lifetime = float(args.mx_lifetime)

    input_header = None
    with inp.open(newline="", encoding="utf-8-sig") as f,\
         outp.open("w", newline="", encoding="utf-8") as fo,\
         supp.open("w", newline="", encoding="utf-8") as fs:

        r = csv.DictReader(f)
        input_header = r.fieldnames or ["Email", "AuthorName", "BookTitle"]
        w_ok = csv.DictWriter(fo, fieldnames=input_header)
        w_bad = csv.DictWriter(fs, fieldnames=["TimestampUTC","Email","Reason"])
        w_ok.writeheader()
        w_bad.writeheader()

        for row in r:
            raw_email = row.get(args.email_col) or ""
            email = extract_email(raw_email).lower()
            if not email:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": "", "Reason": "missing_email"})
                continue
            if args.require_fields:
                author_val = (row.get(args.author_col) or "").strip()
                title_val = (row.get(args.title_col) or "").strip()
                if not author_val:
                    w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": "missing_author"})
                    continue
                if not title_val:
                    w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": "missing_title"})
                    continue
            if email in seen:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": "duplicate"})
                continue
            seen.add(email)

            ok, reason = precheck(email, disposable, mx_cache, args.no_mx, args.allow_role, resolver)
            if ok:
                row[args.email_col] = email
                w_ok.writerow(row)
            else:
                w_bad.writerow({"TimestampUTC": now_utc(), "Email": email, "Reason": reason})

    if args.drain_in:
        inp.write_text(",".join(input_header or ["Email", "AuthorName", "BookTitle"]) + "\n", encoding="utf-8")
    elif args.overwrite_in:
        inp.write_text(outp.read_text(encoding="utf-8"), encoding="utf-8")

if __name__ == "__main__":
    main()
