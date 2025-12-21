# =========================
# BEFORE PITCHES (TOP PART)
# =========================

import argparse
import csv
import html
import random
import ssl
import smtplib
import time
import os
import fcntl
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from getpass import getpass
from pathlib import Path
from typing import Optional, Tuple, Set, Dict, List
from urllib.parse import quote

# ===== SMTP PRESETS =====
SMTP_PRESETS = {
    "private": ("mail.privateemail.com", 587),  # Namecheap PrivateEmail
    "gmail": ("smtp.gmail.com", 587),           # Google Workspace / Gmail SMTP
}

DEFAULT_DOMAIN = "barnesnobleinfo.com"
DEFAULT_UNSUB_EMAIL = f"unsubscribe@{DEFAULT_DOMAIN}"
DEFAULT_UNSUB_CSV = Path("unsubscribed.csv")     # optional, header: Email
DEFAULT_SUPPRESS_CSV = Path("suppressed.csv")    # optional, header: Email

# ===== SIGNATURES (inline image via CID) =====
SIGNATURE_CID = "sigimg"

SIGNATURE_BY_FROM: Dict[str, str] = {
    # --- Gmail 4 accounts (each different) ---
    "corporate@barnesnobleinfo.com": "sig_gmail_corporate.png",
    "sally@littlebrowncoinfo.com":     "sig_gmail_sally.png",
    "jordan@barnesnobleinfo.com":    "sig_gmail_jordan.png",
    "josefina@barnesnobleinfo.com":  "sig_gmail_josefina.png",

    # --- Astra 7 accounts (ALL SAME image) ---
    "megan@astraproductionsbyjc.com":   "sig_astra.png",
    "alex@astraproductionsbyjc.com":    "sig_astra.png",
    "kentc@astraproductionsbyjc.com":   "sig_astra.png",
    "zachking@astraproductionsbyjc.com":"sig_astra.png",
    "jc@astraproductionsbyjc.com":      "sig_astra.png",
    "jordanA@astraproductionsbyjc.com": "sig_astra.png",
    "astra@astraproductionsbyjc.com":   "sig_astra.png",

    # --- PrivateEmail 5 accounts (each different) ---
    "marketing@barnesnobleinfo.com":      "sig_private_marketing.png",
    "jordan_kendrick@barnesnobleinfo.com":"sig_private_jordan.png",
    "jodi_horowitz@barnesnobleinfo.com":  "sig_private_jodi.png",
    "alison@barnesnobleinfo.com":         "sig_private_alison.png",
    "fiorela@barnesnobleinfo.com":        "sig_private_fiorela.png",
}

# OPTIONAL: per-pitch override (wins over SIGNATURE_BY_FROM)
SIGNATURE_BY_PITCH = {
    # "pitch2": "sig_special.png",
}

PITCHES = {
    "pitch1": {
        "subject": "Cinematic first impression for your book",
        "body": """Dear {AuthorName}, 

Readers decide fast: Do I feel anything?

{BookTitle} has “I can see this” energy—it reads like scenes, not just sentences.

My name is Annette Danek-Akey, Chief Supply Chain Officer, and I oversee all operations for the Barnes & Noble Distribution Centers. We help authors place their books on consignment in B&N physical bookstores across the United States.

I’m reaching out because we partner with Astra Productions, a team we trust to create cinematic book trailers and clean author/book pages that convert interest into clicks.

What we’d build for {BookTitle}:
• a short cinematic trailer that makes the tone and stakes felt immediately
• a focused book page with your cover, best review lines, and clear buy buttons

This also sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, send 3 quick details:
• what you want readers to feel (e.g., eerie, hopeful, heart-racing)
• 1–2 must-include lines (tagline / review / award)
• anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.
(Comparable cinematic trailers are often $3,000+.)

Best regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
            },

    "pitch2": {
        "subject": "Barnes & Noble Physical Placement",
        "body": """Hi {AuthorName},

My name is Jordan Kendrick, and I manage marketing and distribution programs that help authors place their books on consignment in B&N physical bookstores across the United States.

I am reaching out to invite you to participate in our bookstore consignment program, which is designed to get qualified titles onto physical shelves and in front of in-store readers.

Because we receive many requests, we only invite books that we believe are professionally produced, marketable, and a good fit for general readers. In evaluating a title, we consider the book’s subject, production and print quality, retail price and terms, and the clarity and professionalism of the writing.

How the program works:

We handle the printing and production of your books based on the quantity you choose.
You cover the shipping and handling costs to deliver the books to participating stores; this is standard practice for consignment arrangements.
You receive 85% of the total sales from this consignment program, equal to $1.50 for every copy sold. Royalties and a detailed sales report will be sent every quarter (within three months after the close of each quarter).
As an added benefit, we also prepare and submit proposals to traditional publishers on your behalf. Having your book available in physical bookstores strengthens your position by demonstrating real-world demand and commercial potential.

Your total investment for initial physical stocking is:

$1,000 for 3,500 copies
$750 for 2,500 copies
$500 for 1,500 copies
$250 for 750 copies
You may select the print quantity that best fits your goals and budget. Your only cost is shipping.

If you are interested in moving forward, please let me know, and I will send the next steps along with a simple agreement for your review.

Have a wonderful day!

Sincerely,
Jordan Kendrick
Marketing director

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

    "pitch3": {
        "subject": "Barnes & Noble Physical Placement",
        "body": """Hi {AuthorName},

My name is Jodi Horowitz, and I manage marketing and distribution programs that help authors place their books on consignment in B&N physical bookstores across the United States.

I am reaching out to invite you to participate in our bookstore consignment program, which is designed to get qualified titles onto physical shelves and in front of in-store readers.

Because we receive many requests, we only invite books that we believe are professionally produced, marketable, and a good fit for general readers. In evaluating a title, we consider the book’s subject, production and print quality, retail price and terms, and the clarity and professionalism of the writing.

How the program works:

We handle the printing and production of your books based on the quantity you choose.
You cover the shipping and handling costs to deliver the books to participating stores; this is standard practice for consignment arrangements.
You receive 85% of the total sales from this consignment program, equal to $1.50 for every copy sold. Royalties and a detailed sales report will be sent every quarter (within three months after the close of each quarter).
As an added benefit, we also prepare and submit proposals to traditional publishers on your behalf. Having your book available in physical bookstores strengthens your position by demonstrating real-world demand and commercial potential.

Your total investment for initial physical stocking is:

$1,000 for 3,500 copies
$750 for 2,500 copies
$500 for 1,500 copies
$250 for 750 copies
You may select the print quantity that best fits your goals and budget. Your only cost is shipping.

If you are interested in moving forward, please let me know, and I will send the next steps along with a simple agreement for your review.

Have a wonderful day!

Sincerely,
Jodi Horowitz
Customer Marketing Director

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

    "pitch4": {
        "subject": "Barnes & Noble Physical Placement",
        "body": """Hi {AuthorName},

My name is Alison Aguair, and I manage marketing and distribution programs that help authors place their books on consignment in B&N physical bookstores across the United States.

I am reaching out to invite you to participate in our bookstore consignment program, which is designed to get qualified titles onto physical shelves and in front of in-store readers.

Because we receive many requests, we only invite books that we believe are professionally produced, marketable, and a good fit for general readers. In evaluating a title, we consider the book’s subject, production and print quality, retail price and terms, and the clarity and professionalism of the writing.

How the program works:

We handle the printing and production of your books based on the quantity you choose.
You cover the shipping and handling costs to deliver the books to participating stores; this is standard practice for consignment arrangements.
You receive 85% of the total sales from this consignment program, equal to $1.50 for every copy sold. Royalties and a detailed sales report will be sent every quarter (within three months after the close of each quarter).
As an added benefit, we also prepare and submit proposals to traditional publishers on your behalf. Having your book available in physical bookstores strengthens your position by demonstrating real-world demand and commercial potential.

Your total investment for initial physical stocking is:

$1,000 for 3,500 copies
$750 for 2,500 copies
$500 for 1,500 copies
$250 for 750 copies
You may select the print quantity that best fits your goals and budget. Your only cost is shipping.

If you are interested in moving forward, please let me know, and I will send the next steps along with a simple agreement for your review.

Have a wonderful day!

Sincerely,
Alison Aguiar 
Senior Manager, Marketing Operations
Barnesnoble Inc.

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

    "pitch5": {
        "subject": "Barnes & Noble Physical Placement",
        "body": """Hi {AuthorName},

My name is Fiorella DeLima, and I manage marketing and distribution programs that help authors place their books on consignment in B&N physical bookstores across the United States.

I am reaching out to invite you to participate in our bookstore consignment program, which is designed to get qualified titles onto physical shelves and in front of in-store readers.

Because we receive many requests, we only invite books that we believe are professionally produced, marketable, and a good fit for general readers. In evaluating a title, we consider the book’s subject, production and print quality, retail price and terms, and the clarity and professionalism of the writing.

How the program works:

We handle the printing and production of your books based on the quantity you choose.
You cover the shipping and handling costs to deliver the books to participating stores; this is standard practice for consignment arrangements.
You receive 85% of the total sales from this consignment program, equal to $1.50 for every copy sold. Royalties and a detailed sales report will be sent every quarter (within three months after the close of each quarter).
As an added benefit, we also prepare and submit proposals to traditional publishers on your behalf. Having your book available in physical bookstores strengthens your position by demonstrating real-world demand and commercial potential.

Your total investment for initial physical stocking is:

$1,000 for 3,500 copies
$750 for 2,500 copies
$500 for 1,500 copies
$250 for 750 copies
You may select the print quantity that best fits your goals and budget. Your only cost is shipping.

If you are interested in moving forward, please let me know, and I will send the next steps along with a simple agreement for your review.

Have a wonderful day!

Sincerely,
Fiorella deLima
Barnes & Noble
Production Manager 

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”)."""

  },

  # ===== GMAIL / WORKSPACE PITCHES (1–5) =====
  "gmail1": {
    "subject": "Cinematic first impression for your book",
    "body": """Dear {AuthorName},

Readers decide fast: Do I feel anything?

{BookTitle} has “I can see this” energy—it reads like scenes, not just sentences.

My name is Annette Danek-Akey, Chief Supply Chain Officer, and I oversee all operations for the Barnes & Noble Distribution Centers. We help authors place their books on consignment in B&N physical bookstores across the United States.

I’m reaching out because we partner with Astra Productions, a team we trust to create cinematic book trailers and clean author/book pages that convert interest into clicks.

What we’d build for {BookTitle}:
• a short cinematic trailer that makes the tone and stakes felt immediately
• a focused book page with your cover, best review lines, and clear buy buttons

This also sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, send 3 quick details:
• what you want readers to feel (e.g., eerie, hopeful, heart-racing)
• 1–2 must-include lines (tagline / review / award)
• anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.
(Comparable cinematic trailers are often $3,000+.)

Best regards,
Annette Danek-Akey
Chief Supply Chain Officer
Barnes & Noble 

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "gmail2": {
    "subject": "Little, Brown - Hachette Book Group Traditional Publishing Proposal",
    "body": """Hi {AuthorName},

My name is Sally Kim, and I am the Acquisition Director and Publisher at Little, Brown - Hachette Book Group. I help authors place their books on consignment in B&N physical bookstores across the United States.

I am reaching out to invite you to participate in our bookstore consignment program, which is designed to get qualified titles onto physical shelves and in front of in-store readers.

Because we receive many requests, we only invite books that we believe are professionally produced, marketable, and a good fit for general readers. In evaluating a title, we consider the book’s subject, production and print quality, retail price and terms, and the clarity and professionalism of the writing.

How the program works:

We handle the printing and production of your books based on the quantity you choose.
You cover the shipping and handling costs to deliver the books to participating stores; this is standard practice for consignment arrangements.
You receive 85% of the total sales from this consignment program, equal to $1.50 for every copy sold. Royalties and a detailed sales report will be sent every quarter (within three months after the close of each quarter).
As an added benefit, we also prepare and submit proposals to traditional publishers on your behalf. Having your book available in physical bookstores strengthens your position by demonstrating real-world demand and commercial potential.

Your total investment for initial physical stocking is:

$1,000 for 3,500 copies
$750 for 2,500 copies
$500 for 1,500 copies
$250 for 750 copies
You may select the print quantity that best fits your goals and budget. Your only cost is shipping.

If you are interested in moving forward, please let me know, and I will send the next steps along with a simple agreement for your review.

Have a wonderful day!

Sincerely,
Sally Kim
Pres and Publisher of Little, Brown and Company
New York City
United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "gmail3": {
        "subject": "Barnes & Noble Physical Placement",
        "body": """Hi {AuthorName},

My name is Jordan Kendrick, and I manage marketing and distribution programs that help authors place their books on consignment in B&N physical bookstores across the United States.

I am reaching out to invite you to participate in our bookstore consignment program, which is designed to get qualified titles onto physical shelves and in front of in-store readers.

Because we receive many requests, we only invite books that we believe are professionally produced, marketable, and a good fit for general readers. In evaluating a title, we consider the book’s subject, production and print quality, retail price and terms, and the clarity and professionalism of the writing.

How the program works:

We handle the printing and production of your books based on the quantity you choose.
You cover the shipping and handling costs to deliver the books to participating stores; this is standard practice for consignment arrangements.
You receive 85% of the total sales from this consignment program, equal to $1.50 for every copy sold. Royalties and a detailed sales report will be sent every quarter (within three months after the close of each quarter).
As an added benefit, we also prepare and submit proposals to traditional publishers on your behalf. Having your book available in physical bookstores strengthens your position by demonstrating real-world demand and commercial potential.

Your total investment for initial physical stocking is:

$1,000 for 3,500 copies
$750 for 2,500 copies
$500 for 1,500 copies
$250 for 750 copies
You may select the print quantity that best fits your goals and budget. Your only cost is shipping.

If you are interested in moving forward, please let me know, and I will send the next steps along with a simple agreement for your review.

Have a wonderful day!

Sincerely,
Jordan Kendrick
Barnes & Noble Inc.
Marketing director
United States

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "gmail4": {
    "subject": "Cinematic first impression for your book",
    "body": """Hi {AuthorName}, 

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
Josefina Stenstrom, Email Marketing Specialist
Barnes & Noble Inc.
United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
""" 

    },

  "gmail5": {
    "subject": "Should I close this out?",
    "body": """Hi {AuthorName},

Just checking—should I close this out?

If you want your book to stand out more online, reply with your book link (or title + synopsis) and I’ll send a quick concept + examples.
If not, no worries—I won’t follow up again.

Best regards,
B&N Marketing Team

Opt out: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },
    
  # ===== GMAIL / WORKSPACE PITCHES (1–5) =====
  "astra1": {
    "subject": "Cinematic first impression for your book",
    "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
 Sofia Margaret, Creative Producer
 Astra Productions
 United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "astra2": {
    "subject": "Cinematic first impression for your book",
    "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
 Windelle JC, CEO
 Astra Productions
 United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "astra3": {
        "subject": "Quick Idea to make your Book stand out online",
        "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
Jordan Miller, Author Outreach Specialist
Astra Productions
United States          

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "astra4": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
Kent Rivera, Client Success Coordinator
Astra Productions
United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "astra5": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
Zach King, Web & Trailer Specialist
Astra Productions
United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

     "astra6": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
Alex Carter, Marketing Team Lead
Astra Productions
United States

Opt out: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

       "astra7": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Most readers don’t decide in a paragraph. They decide in a split-second: Do I feel anything?
That’s why I’m reaching out—{BookTitle} has “I can see this” energy. It reads like scenes, not just sentences.

At Astra Productions, we turn that first split-second into a movie-preview moment:
 • a short cinematic trailer that makes the tone and stakes felt fast
 • a clean book page where the trailer lives with your cover, strongest review lines, and clear buy buttons (so when someone feels it, they can click immediately)

If you’re open to it, send 3 quick details you’d want included:

what you want readers to feel (e.g., eerie, hopeful, heart-racing)

1–2 must-include lines (tagline / review / award)

anything to avoid (spoilers)

I’ll reply with two trailer opening concepts for {BookTitle}, a simple page layout, and 2–3 examples—so you can judge the fit before deciding.
Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
Megan
Production Coordinator
Astra Productions

Opt out: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },  
}


def norm_email(s: str) -> str:
    _, addr = parseaddr(s or "")
    return addr.strip().lower()


def make_unsub_mailto(unsub_email: str) -> str:
    return f"mailto:{unsub_email}?subject={quote('unsubscribe')}&body={quote('unsubscribe')}"


def parse_ts(ts: str) -> Optional[datetime]:
    ts = (ts or "").strip()
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def is_external(addr: str, my_domains: Set[str]) -> bool:
    if "@" not in addr:
        return False
    return addr.split("@", 1)[1] not in my_domains


def read_rows(path: Path) -> List[Dict[str, str]]:
    def clean(v) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return " ".join(str(x).strip() for x in v if x is not None).strip()
        return str(v).strip()

    rows: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            row: Dict[str, str] = {}
            for k, v in r.items():
                if k is None:
                    continue
                key = str(k).strip().lstrip("\ufeff")
                row[key] = clean(v)
            rows.append(row)
    return rows


def load_emails_from_csv(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    out: Set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def load_already_done(sent_log: Path) -> Set[str]:
    if not sent_log.exists():
        return set()
    out: Set[str] = set()
    with sent_log.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = (r.get("Status") or "").strip().upper()
            if st not in ("SENT", "INVALID"):
                continue
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def log_row(sent_log: Path, email: str, status: str, info: str = "") -> None:
    new_file = not sent_log.exists()
    with sent_log.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
        if new_file:
            w.writeheader()
        w.writerow({
            "TimestampUTC": datetime.now(timezone.utc).isoformat(),
            "Email": email,
            "Status": status,
            "Info": (info or "")[:300],
        })


def text_to_html(body_text: str, unsub_mailto: str, cid: Optional[str]) -> str:
    """
    HTML version:
    - converts {UnsubMailto} into a clickable link
    - replaces {SIGIMG} with an inline CID image IF cid is provided
    - removes {SIGIMG} if cid is not provided
    """
    safe = html.escape(body_text)

    # clickable unsubscribe
    safe = safe.replace(
        html.escape(unsub_mailto),
        f"<a href='{html.escape(unsub_mailto)}'>unsubscribe</a>"
    )

    # signature marker replacement
    if cid:
        sig_tag = (
            f"<img src='cid:{cid}' alt='Signature' "
            "style='max-width:320px;height:auto;display:block;margin-top:10px;'>"
        )
        safe = safe.replace("{SIGIMG}", sig_tag)
    else:
        safe = safe.replace("{SIGIMG}", "")

    safe = safe.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<html><body><p>{safe}</p></body></html>"


def build_message(
    from_email: str,
    to_email: str,
    author: str,
    book_title: str,
    subject: str,
    body_template: str,
    unsub_email: str,
    signature_file: Optional[Path] = None,
) -> EmailMessage:
    unsub_mailto = make_unsub_mailto(unsub_email)

    author = (author or "there").strip()
    book_title = (book_title or "").strip() or "your book"

    body_text = body_template.format(
        AuthorName=author,
        BookTitle=book_title,
        UnsubEmail=unsub_email,
        UnsubMailto=unsub_mailto,
        SIGIMG="{SIGIMG}",   # <-- prevents KeyError and keeps the marker for HTML
    )

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = from_email
    msg["List-Unsubscribe"] = f"<mailto:{unsub_email}?subject=unsubscribe>"

    # Plain text: remove marker so recipients don't see "{SIGIMG}"
    msg.set_content(body_text.replace("{SIGIMG}", "").strip())

    cid = SIGNATURE_CID if (signature_file and signature_file.exists()) else None
    html_body = text_to_html(body_text, unsub_mailto, cid=cid)
    msg.add_alternative(html_body, subtype="html")

    # Attach inline signature only if pitch contains {SIGIMG} AND signature_file exists
    if cid and signature_file and signature_file.exists() and "{SIGIMG}" in body_text:
        img_bytes = signature_file.read_bytes()
        msg.get_payload()[-1].add_related(
            img_bytes,
            maintype="image",
            subtype="png",
            cid=f"<{cid}>",
            filename=signature_file.name,
            disposition="inline",
        )

    return msg


# ===== SMTP session =====
def smtp_login(host: str, port: int, user: str, pw: str) -> smtplib.SMTP:
    s = smtplib.SMTP(host, port, timeout=30)
    s.ehlo()
    s.starttls(context=ssl.create_default_context())
    s.ehlo()
    s.login(user, pw)
    return s


def smtp_close(s: Optional[smtplib.SMTP]) -> None:
    if not s:
        return
    try:
        s.quit()
    except Exception:
        try:
            s.close()
        except Exception:
            pass


# ===== Error classification =====
def _decode_smtp_err(x) -> str:
    if isinstance(x, (bytes, bytearray)):
        return x.decode(errors="ignore")
    return str(x)


def classify_smtp(code: Optional[int], text: str) -> str:
    t = (text or "").lower()

    if ("5.4.5" in t) or ("daily user sending limit exceeded" in t) or ("too many unique external" in t) or ("has exceeded the gmail sending limit" in t):
        return "HARD_LIMIT"

    if code is not None and 400 <= int(code) <= 499:
        return "TEMP_THROTTLE"
    if ("rate" in t and "limit" in t) or ("try again later" in t) or ("temporarily" in t and "limit" in t):
        return "TEMP_THROTTLE"

    if ("5.1.1" in t) or ("user unknown" in t) or ("no such user" in t) or ("recipient address rejected" in t and "unknown" in t):
        return "BAD_RECIPIENT"

    return "OTHER"


def extract_code_text_from_exception(e: Exception) -> Tuple[Optional[int], str]:
    code = getattr(e, "smtp_code", None)
    raw = getattr(e, "smtp_error", "")
    text = _decode_smtp_err(raw)
    try:
        if code is not None:
            code = int(code)
    except Exception:
        code = None
    return code, text


# ===== Rolling 1h guard (PrivateEmail shared bucket) =====
def _parse_ts_safe(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((ts or "").strip().replace("Z", "+00:00"))
    except Exception:
        return None


def domain_wait_for_slot(domain_log_path: Path, max_messages_1h: int, jitter_sec: int = 5) -> None:
    """
    Domain-wide rolling 60-min limiter using a file lock.
    Counts SENT + SLOT in last hour. Writes SLOT reservation to prevent races.
    """
    if max_messages_1h <= 0:
        return

    domain_log_path.parent.mkdir(parents=True, exist_ok=True)

    if not domain_log_path.exists():
        with domain_log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
            w.writeheader()

    while True:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)

        with domain_log_path.open("r+", newline="", encoding="utf-8-sig") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            f.seek(0)
            rows = list(csv.DictReader(f))

            times: List[datetime] = []
            for r in rows:
                st = (r.get("Status") or "").strip().upper()
                if st not in ("SENT", "SLOT"):
                    continue
                t = _parse_ts_safe(r.get("TimestampUTC") or "")
                if t and t >= cutoff:
                    times.append(t)

            times.sort()
            used = len(times)

            if used < max_messages_1h:
                f.seek(0, os.SEEK_END)
                w = csv.DictWriter(f, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
                w.writerow({
                    "TimestampUTC": now.isoformat(),
                    "Email": "",
                    "Status": "SLOT",
                    "Info": "reserve",
                })
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return

            earliest = (times[0] + timedelta(hours=1)) if times else (now + timedelta(seconds=30))
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        wait_s = max(1, int((earliest - datetime.now(timezone.utc)).total_seconds())) + random.randint(0, jitter_sec)
        time.sleep(wait_s)


def sleep_with_jitter(seconds: int, jitter: int = 10) -> None:
    time.sleep(max(1, int(seconds)) + random.randint(0, max(0, int(jitter))))


def append_suppressed_email(suppress_csv_path: Path, email_addr: str) -> None:
    if not email_addr:
        return
    if not suppress_csv_path.exists():
        with suppress_csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Email"])
            w.writeheader()
            w.writerow({"Email": email_addr})
    else:
        with suppress_csv_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Email"])
            w.writerow({"Email": email_addr})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--pitch", required=True, choices=sorted(PITCHES.keys()))
    ap.add_argument("--provider", choices=["private", "gmail"], required=True)

    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--unsub", default=DEFAULT_UNSUB_EMAIL)
    ap.add_argument("--unsub_csv", default=str(DEFAULT_UNSUB_CSV))
    ap.add_argument("--suppress_csv", default=str(DEFAULT_SUPPRESS_CSV))
    ap.add_argument("--my_domains", default=DEFAULT_DOMAIN)

    ap.add_argument("--max_unique_external_24h", type=int, default=1900)
    ap.add_argument("--max_messages_24h", type=int, default=1900)

    ap.add_argument("--max_per_run", type=int, default=0)
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--preflight", action="store_true")

    ap.add_argument("--max_messages_1h", type=int, default=0)
    ap.add_argument("--domain_log", default="")
    ap.add_argument("--suppress_invalid", action="store_true")

    args = ap.parse_args()

    host, port = SMTP_PRESETS[args.provider]
    pitch = PITCHES[args.pitch]
    subject = (pitch.get("subject") or "").strip()
    body_template = (pitch.get("body") or "").strip()

    csv_path = Path(args.csv)
    log_path = Path(args.log)
    unsub_csv_path = Path(args.unsub_csv)
    suppress_csv_path = Path(args.suppress_csv)

    if not csv_path.exists():
        print("ERROR missing:", csv_path)
        return

    my_domains: Set[str] = {d.strip().lower() for d in (args.my_domains or "").split(",") if d.strip()}
    if not my_domains:
        my_domains = {DEFAULT_DOMAIN}

    rows = read_rows(csv_path)
    already_done = load_already_done(log_path)
    unsubbed = load_emails_from_csv(unsub_csv_path)
    suppressed = load_emails_from_csv(suppress_csv_path)

    pending: List[Dict[str, str]] = []
    for r in rows:
        email_addr = norm_email(r.get("Email") or "")
        if not email_addr:
            continue
        if email_addr in already_done or email_addr in unsubbed or email_addr in suppressed:
            continue
        pending.append(r)

    print(f"PROVIDER: {args.provider} | HOST: {host}:{port}")
    print(f"PITCH: {args.pitch} | CSV: {csv_path.name} | Pending: {len(pending)} | Interval: {args.interval}s")
    if args.dry_run:
        print("DRY RUN: no emails will be sent.")
    if not pending:
        print("Nothing to send.")
        return

    domain_log_path = Path(args.domain_log) if args.domain_log else log_path

    if args.preflight:
        if args.provider == "private" and args.max_messages_1h:
            print(f"DOMAIN LOG: {domain_log_path.name} | cap_1h={args.max_messages_1h}")
        print("PREFLIGHT: ok (no sending).")
        return

    from_user = norm_email(input("From (email address you are logging in as): "))
    pw = "" if args.dry_run else getpass("Password (Gmail uses App Password): ").strip()
    unsub_email = from_user

    # Choose signature file:
    # - only applies if the pitch body contains {SIGIMG}
    pitch_key = args.pitch
    sig_name = (SIGNATURE_BY_PITCH.get(pitch_key) or SIGNATURE_BY_FROM.get(from_user) or "")
    sig_name = sig_name.strip()
    sig_path = Path(sig_name) if (sig_name and "{SIGIMG}" in body_template) else None

    smtp: Optional[smtplib.SMTP] = None
    sent_this_run = 0

    def ensure_smtp() -> smtplib.SMTP:
        nonlocal smtp
        if smtp is None:
            smtp = smtp_login(host, port, from_user, pw)
        return smtp

    def send_one(msg: EmailMessage) -> None:
        """
        PrivateEmail: connect per message (reduces DISCONNECTED loops)
        Gmail: keep connection open
        """
        nonlocal smtp
        if args.provider == "private":
            smtp_close(smtp)
            smtp = None
            s = ensure_smtp()
            s.send_message(msg)
            smtp_close(s)
            smtp = None
        else:
            ensure_smtp().send_message(msg)

    def backoff_seconds() -> int:
        base = max(180, int(args.interval) * 4)
        return base + random.randint(0, 45)

    try:
        if not args.dry_run and args.provider == "gmail":
            ensure_smtp()

        for i, r in enumerate(pending, start=1):
            to_email = norm_email(r.get("Email") or "")
            if not to_email:
                continue

            if args.max_per_run and sent_this_run >= args.max_per_run:
                print(f"STOP: reached --max_per_run={args.max_per_run}")
                break

            author = (r.get("AuthorName") or "there").strip()
            book_title = (r.get("BookTitle") or r.get("Title") or "").strip()

            msg = build_message(
                from_user, to_email, author, book_title,
                subject, body_template, unsub_email,
                signature_file=sig_path
            )

            try:
                if args.dry_run:
                    log_row(log_path, to_email, "DRYRUN", "not_sent")
                    print(f"[{i}/{len(pending)}] DRYRUN -> {to_email}")
                else:
                    if args.provider == "private" and args.max_messages_1h:
                        domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                    send_one(msg)

                    log_row(log_path, to_email, "SENT")
                    print(f"[{i}/{len(pending)}] SENT -> {to_email}")
                    sent_this_run += 1

                    if args.provider == "private" and args.max_messages_1h and domain_log_path != log_path:
                        log_row(domain_log_path, to_email, "SENT")

            except smtplib.SMTPRecipientsRefused as e:
                rec = e.recipients.get(to_email) or next(iter(e.recipients.values()), None)
                if rec:
                    code = rec[0]
                    text = _decode_smtp_err(rec[1])
                    cls = classify_smtp(int(code) if code is not None else None, text)

                    if cls == "BAD_RECIPIENT":
                        log_row(log_path, to_email, "INVALID", f"{code} {text}")
                        print(f"[{i}/{len(pending)}] INVALID -> {to_email} :: {code} {text}")
                        if args.suppress_invalid:
                            append_suppressed_email(suppress_csv_path, to_email)
                        continue

                    log_row(log_path, to_email, "ERROR", f"{code} {text}")
                    print(f"[{i}/{len(pending)}] RECIPIENT ERROR -> {to_email} :: {code} {text}")
                    continue

                log_row(log_path, to_email, "ERROR", str(e))
                print(f"[{i}/{len(pending)}] RECIPIENT ERROR -> {to_email} :: {e}")
                continue

            except smtplib.SMTPAuthenticationError as e:
                log_row(log_path, to_email, "ERROR", f"auth_failed: {e}")
                print(f"[{i}/{len(pending)}] AUTH ERROR (stop) -> {to_email} :: {e}")
                break

            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPHeloError) as e:
                log_row(log_path, to_email, "ERROR", f"disconnected: {e}")
                print(f"[{i}/{len(pending)}] DISCONNECTED -> reconnecting and retrying once...")

                smtp_close(smtp)
                smtp = None
                sleep_with_jitter(max(args.interval, 60), jitter=10)

                try:
                    if args.provider == "private" and args.max_messages_1h:
                        domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                    send_one(msg)

                    log_row(log_path, to_email, "SENT", "reconnect_ok")
                    print(f"[{i}/{len(pending)}] SENT (reconnect) -> {to_email}")
                    sent_this_run += 1

                    if args.provider == "private" and args.max_messages_1h and domain_log_path != log_path:
                        log_row(domain_log_path, to_email, "SENT")

                except Exception as e2:
                    code2, text2 = extract_code_text_from_exception(e2)
                    log_row(log_path, to_email, "ERROR", f"reconnect_failed: {code2} {text2}")
                    print(f"[{i}/{len(pending)}] ERROR (stop) -> {to_email} :: {code2} {text2}")
                    break

            except (smtplib.SMTPDataError, smtplib.SMTPResponseException) as e:
                code, text = extract_code_text_from_exception(e)
                cls = classify_smtp(code, text)

                if cls == "BAD_RECIPIENT":
                    log_row(log_path, to_email, "INVALID", f"{code} {text}")
                    print(f"[{i}/{len(pending)}] INVALID -> {to_email} :: {code} {text}")
                    if args.suppress_invalid:
                        append_suppressed_email(suppress_csv_path, to_email)
                    continue

                if cls == "TEMP_THROTTLE":
                    log_row(log_path, to_email, "ERROR", f"{code} {text}")
                    wait_s = backoff_seconds()
                    print(f"[{i}/{len(pending)}] THROTTLED -> backing off {wait_s}s and retrying once...")

                    time.sleep(wait_s)
                    smtp_close(smtp)
                    smtp = None
                    sleep_with_jitter(max(args.interval, 60), jitter=10)

                    try:
                        if args.provider == "private" and args.max_messages_1h:
                            domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                        send_one(msg)

                        log_row(log_path, to_email, "SENT", "throttle_retry_ok")
                        print(f"[{i}/{len(pending)}] SENT (retry) -> {to_email}")
                        sent_this_run += 1

                        if args.provider == "private" and args.max_messages_1h and domain_log_path != log_path:
                            log_row(domain_log_path, to_email, "SENT")

                        continue
                    except Exception as e2:
                        code2, text2 = extract_code_text_from_exception(e2)
                        log_row(log_path, to_email, "ERROR", f"retry_failed: {code2} {text2}")
                        print(f"[{i}/{len(pending)}] ERROR (stop) -> {to_email} :: {code2} {text2}")
                        break

                log_row(log_path, to_email, "ERROR", f"{code} {text}")
                print(f"[{i}/{len(pending)}] ERROR -> {to_email} :: {code} {text}")

            except Exception as e:
                log_row(log_path, to_email, "ERROR", str(e))
                print(f"[{i}/{len(pending)}] ERROR -> {to_email} :: {e}")

            if i < len(pending):
                sleep_with_jitter(args.interval, jitter=10)

        print("Done.")

    finally:
        smtp_close(smtp)

if __name__ == "__main__":
    main()
