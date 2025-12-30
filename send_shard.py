# =========================
# BEFORE PITCHES (TOP PART)
# =========================

import argparse
import base64
import csv
import html
import random
import ssl
import smtplib
import time
import os
import fcntl
import sys
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

DEFAULT_DOMAIN = "barnesnoblemarketing.com"
DEFAULT_UNSUB_EMAIL = f"unsubscribe@{DEFAULT_DOMAIN}"
DEFAULT_UNSUB_CSV = Path("unsubscribed.csv")     # optional, header: Email
DEFAULT_SUPPRESS_CSV = Path("suppressed.csv")    # optional, header: Email

PROVIDER_LIMIT_DEFAULTS = {
    "private": {"max_messages_1h": 50},
    "gmail": {"max_messages_24h": 100, "max_unique_external_24h": 100},
}

PROFILES: Dict[str, Dict[str, object]] = {
    # Gmail example (kept for reference)
    "gmail_megan": {
        "provider": "gmail",
        "csv": "recipients_astra7.csv",
        "log": "astra_megan_log.csv",
        "pitch": "astra7",
        "from_email": "megan@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_MEGAN_APP_PW",
    },
    "gmail_astra": {
        "provider": "gmail",
        "csv": "recipients_astra1.csv",
        "log": "astra_jc_log.csv",
        "pitch": "astra1",
        "from_email": "astra@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_ASTRA_APP_PW",
    },
    "gmail_jc": {
        "provider": "gmail",
        "csv": "recipients_astra2.csv",
        "log": "astra_jc_log.csv",
        "pitch": "astra2",
        "from_email": "jc@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_JC_APP_PW",
    },
    "gmail_jordanA": {
        "provider": "gmail",
        "csv": "recipients_astra3.csv",
        "log": "astra_jordanA_log.csv",
        "pitch": "astra3",
        "from_email": "jordan@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_JORDAN_A_APP_PW",
    },
    "gmail_kent": {
        "provider": "gmail",
        "csv": "recipients_astra4.csv",
        "log": "astra_kentc_log.csv",
        "pitch": "astra4",
        "from_email": "kent.c@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_KENT_APP_PW",
    },
    "gmail_zachking": {
        "provider": "gmail",
        "csv": "recipients_astra5.csv",
        "log": "astra_zachking_log.csv",
        "pitch": "astra5",
        "from_email": "zachking@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_ZACHKING_APP_PW",
    },
    "gmail_alex": {
        "provider": "gmail",
        "csv": "recipients_astra6.csv",
        "log": "astra_alex_log.csv",
        "pitch": "astra6",
        "from_email": "alex.c@astraproductionsbyjc.com",
        "my_domains": "barnesnobleinfo.com,astraproductionsbyjc.com",
        "interval": 240,
        "batch_size": 10,
        "cooldown_seconds": 1000,
        "repeat": True,
        "max_total": 120,
        "max_messages_24h": 150,
        "max_unique_external_24h": 150,
        "suppress_invalid": True,
        "password_env": "GMAIL_ALEX_APP_PW",
    },
    # Private mailboxes (trial plan: ~4/hour each, 20/day each, shared domain 50/hour)
    "private_annet": {
        "provider": "private",
        "csv": "recipients_1.csv",
        "log": "private_annet_log.csv",
        "pitch": "pitch1",
        "from_email": "annettedanek-akey@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 900,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "password_env": "PRIVATE_ANNET_APP_PW",
    },
    "private_jordan": {
        "provider": "private",
        "csv": "recipients_2.csv",
        "log": "private_jordan_kendrick_log.csv",
        "pitch": "pitch2",
        "from_email": "jordankendrick@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 920,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "password_env": "PRIVATE_JORDAN_APP_PW",
    },
    "private_jodi": {
        "provider": "private",
        "csv": "recipients_3.csv",
        "log": "private_jodi_horowitz_log.csv",
        "pitch": "pitch3",
        "from_email": "jodihorowitz@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 930,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "password_env": "PRIVATE_JODI_APP_PW",
    },
    "private_alison": {
        "provider": "private",
        "csv": "recipients_4.csv",
        "log": "private_alison_log.csv",
        "pitch": "pitch4",
        "from_email": "alisonaguair@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 940,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "password_env": "PRIVATE_ALISON_APP_PW",
    },
    "private_fiorela": {
        "provider": "private",
        "csv": "recipients_5.csv",
        "log": "private_fiorela_log.csv",
        "pitch": "pitch5",
        "from_email": "fiorelladelima@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 950,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "password_env": "PRIVATE_FIORELA_APP_PW",
    },
    "sendgrid_annet": {
        "provider": "sendgrid",
        "csv": "recipients_1.csv",
        "log": "private_annet_log.csv",
        "pitch": "pitch1",
        "from_email": "annettedanek-akey@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 900,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
    },
    "sendgrid_jordan": {
        "provider": "sendgrid",
        "csv": "recipients_2.csv",
        "log": "private_jordan_kendrick_log.csv",
        "pitch": "pitch2",
        "from_email": "jordankendrick@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 920,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
    },
    "sendgrid_jodi": {
        "provider": "sendgrid",
        "csv": "recipients_3.csv",
        "log": "private_jodi_horowitz_log.csv",
        "pitch": "pitch3",
        "from_email": "jodihorowitz@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 930,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
    },
    "sendgrid_alison": {
        "provider": "sendgrid",
        "csv": "recipients_4.csv",
        "log": "private_alison_log.csv",
        "pitch": "pitch4",
        "from_email": "alisonaguair@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 940,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
    },
    "sendgrid_fiorela": {
        "provider": "sendgrid",
        "csv": "recipients_5.csv",
        "log": "private_fiorela_log.csv",
        "pitch": "pitch5",
        "from_email": "fiorelladelima@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 950,
        "batch_size": 5,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 20,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
    },
    "gmail_corporate": {
        "provider": "gmail",
        "csv": "recipients_g1.csv",
        "log": "gmail_corporate_log.csv",
        "pitch": "gmail1",
        "from_email": "corporate@barnesnobleinfo.com",
        "my_domains": "barnesnobleinfo.com,littlebrowncoinfo.com,astraproductionsbyjc.com",
        "interval": 300,
        "batch_size": 10,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 40,
        "max_messages_24h": 120,
        "max_unique_external_24h": 120,
        "suppress_invalid": True,
        "password_env": "GMAIL_CORPORATE_APP_PW",
    },
    "gmail_sally": {
        "provider": "gmail",
        "csv": "recipients_g2.csv",
        "log": "gmail_sally_log.csv",
        "pitch": "gmail2",
        "from_email": "sally.kim@littlebrowncoinfo.com",
        "my_domains": "barnesnobleinfo.com,littlebrowncoinfo.com,astraproductionsbyjc.com",
        "interval": 300,
        "batch_size": 10,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 40,
        "max_messages_24h": 120,
        "max_unique_external_24h": 120,
        "suppress_invalid": True,
        "password_env": "GMAIL_SALLY_APP_PW",
    },
    "gmail_jordan": {
        "provider": "gmail",
        "csv": "recipients_g3.csv",
        "log": "gmail_jordan_log.csv",
        "pitch": "gmail3",
        "from_email": "jordan.kendrick@barnesnobleinfo.com",
        "my_domains": "barnesnobleinfo.com,littlebrowncoinfo.com,astraproductionsbyjc.com",
        "interval": 300,
        "batch_size": 10,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 40,
        "max_messages_24h": 120,
        "max_unique_external_24h": 120,
        "suppress_invalid": True,
        "password_env": "GMAIL_JORDAN_APP_PW",
    },
    "gmail_josefina": {
        "provider": "gmail",
        "csv": "recipients_g4.csv",
        "log": "gmail_josefina_log.csv",
        "pitch": "gmail4",
        "from_email": "josefina.stenstrom@barnesnobleinfo.com",
        "my_domains": "barnesnobleinfo.com,littlebrowncoinfo.com,astraproductionsbyjc.com",
        "interval": 300,
        "batch_size": 10,
        "cooldown_seconds": 1200,
        "repeat": True,
        "max_total": 40,
        "max_messages_24h": 120,
        "max_unique_external_24h": 120,
        "suppress_invalid": True,
        "password_env": "GMAIL_JOSEFINA_APP_PW",
    },
}

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
    "jordankendrick@barnesnoblemarketing.com":"sig_private_jordan.png",
    "jodihorowitz@barnesnoblemarketing.com":  "sig_private_jodi.png",
    "alisonaguair@barnesnoblemarketing.com": "sig_private_alison.png",
    "fiorelladelima@barnesnoblemarketing.com": "sig_private_fiorela.png",
    "annettedanek-akey@barnesnoblemarketing.com": "sig_private_annette.png",
}
SIGNATURE_BY_PITCH = {
    }
PITCH1_BODY = """Dear {AuthorName}, 

Your book, "{BookTitle}" reads like scenes, not just sentences.

I'm reaching out because I manage marketing and distribution programs that help authors place their books on B&N physical bookstores across the United States.

We partner with Astra Productions to create two launch assets that make readers feel the book fast:

• 30–60s cinematic trailer (tone + stakes in the opening beats)
• clean, focused book page (cover, hook, proof lines, clear buy buttons)

This sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, reply with:

what you want readers to feel (e.g., eerie / hopeful / heart-racing)
1–2 must-include lines (tagline, review, award)
anything to avoid (spoilers, tropes)

I’ll send back:
• two trailer opening hook concepts for {BookTitle}
• a simple one-page layout
• 2–3 recent examples (so you can judge the fit before deciding)

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""

PITCHES = {
    "pitch1": {
        "subject": "Quick idea for {BookTitle}",
        "body": """Dear {AuthorName}, 

Your book, "{BookTitle}" reads like scenes, not just sentences.

I'm reaching out because I manage marketing and distribution programs that help authors place their books on B&N physical bookstores across the United States.

We partner with Astra Productions to create two launch assets that make readers feel the book fast:

• 30–60s cinematic trailer (tone + stakes in the opening beats)
• clean, focused book page (cover, hook, proof lines, clear buy buttons)

This sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, reply with:

what you want readers to feel (e.g., eerie / hopeful / heart-racing)
1–2 must-include lines (tagline, review, award)
anything to avoid (spoilers, tropes)

I’ll send back:
• two trailer opening hook concepts for {BookTitle}
• a simple one-page layout
• 2–3 recent examples (so you can judge the fit before deciding)

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
            },

    "pitch2": {
        "subject": "Quick idea for {BookTitle}",
        "body": """Hi {AuthorName},

Your book, "{BookTitle}" reads like scenes, not just sentences.

I'm reaching out because I manage marketing and distribution programs that help authors place their books on B&N physical bookstores across the United States.

We partner with Astra Productions to create two launch assets that make readers feel the book fast:

• 30–60s cinematic trailer (tone + stakes in the opening beats)
• clean, focused book page (cover, hook, proof lines, clear buy buttons)

This sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, reply with:

what you want readers to feel (e.g., eerie / hopeful / heart-racing)
1–2 must-include lines (tagline, review, award)
anything to avoid (spoilers, tropes)

I’ll send back:
• two trailer opening hook concepts for {BookTitle}
• a simple one-page layout
• 2–3 recent examples (so you can judge the fit before deciding)

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

    "pitch3": {
        "subject": "Quick idea for {BookTitle}",
        "body": """Hi {AuthorName},

Your book, "{BookTitle}" reads like scenes, not just sentences.

I'm reaching out because I manage marketing and distribution programs that help authors place their books on B&N physical bookstores across the United States.

We partner with Astra Productions to create two launch assets that make readers feel the book fast:

• 30–60s cinematic trailer (tone + stakes in the opening beats)
• clean, focused book page (cover, hook, proof lines, clear buy buttons)

This sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, reply with:

what you want readers to feel (e.g., eerie / hopeful / heart-racing)
1–2 must-include lines (tagline, review, award)
anything to avoid (spoilers, tropes)

I’ll send back:
• two trailer opening hook concepts for {BookTitle}
• a simple one-page layout
• 2–3 recent examples (so you can judge the fit before deciding)

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

    "pitch4": {
        "subject": "Quick idea for {BookTitle}",
        "body": """Hi {AuthorName},

Your book, "{BookTitle}" reads like scenes, not just sentences.
I'm reaching out because I manage marketing and distribution programs that help authors place their books on B&N physical bookstores across the United States.

We partner with Astra Productions to create two launch assets that make readers feel the book fast:

• 30–60s cinematic trailer (tone + stakes in the opening beats)
• clean, focused book page (cover, hook, proof lines, clear buy buttons)

This sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, reply with:

what you want readers to feel (e.g., eerie / hopeful / heart-racing)
1–2 must-include lines (tagline, review, award)
anything to avoid (spoilers, tropes)

I’ll send back:
• two trailer opening hook concepts for {BookTitle}
• a simple one-page layout
• 2–3 recent examples so you can judge the fit before deciding

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

    "pitch5": {
        "subject": "Quick idea for {BookTitle}",
        "body": """Hi {AuthorName},

your book, {BookTitle} has “I can see this” energy—it reads like scenes, not just sentences.

I'm reaching out because I manage marketing and distribution programs that help authors place their books on B&N physical bookstores across the United States.

We partner with Astra Productions to create two launch assets that make readers feel the book fast:

• 30–60s cinematic trailer (tone + stakes in the opening beats)
• clean, focused book page (cover, hook, proof lines, clear buy buttons)

This sets you up for the next step later: if you ever want physical-store placement, these assets make it easier for decision-makers to preview the book fast.

If you’re open to it, reply with:

what you want readers to feel (e.g., eerie / hopeful / heart-racing)
1–2 must-include lines (tagline, review, award)
anything to avoid (spoilers, tropes)

I’ll send back:
• two trailer opening hook concepts for {BookTitle}
• a simple one-page layout
• 2–3 recent examples (so you can judge the fit before deciding)

Investment: Trailer $999 | Book page/website $499 | Bundle $1,299.

Best regards,
{SIGIMG}

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

Readers decide fast: Do I feel anything?

{BookTitle} has “I can see this” energy—it reads like scenes, not just sentences.

My name is Josefina Stenstrom, Email Marketing Specialist of Barnes & Noble. We help authors place their books on consignment in B&N physical bookstores across the United States.

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

Happy Holidays!

I'm Sofia Margaret, Creative Producer of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Sofia Margaret
Creative Producer
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
"""
  },

  "astra2": {
    "subject": "Cinematic first impression for your book",
    "body": """Hi {AuthorName},

Happy Holidays!

I'm Windelle JC, CEO of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Windelle JC
CEO
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
"""
  },

  "astra3": {
        "subject": "Quick Idea to make your Book stand out online",
        "body": """Hi {AuthorName},

Happy Holidays!

I'm Jordan Miller, Author Outreach Specialist of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Jordan Miller
Author Outreach Specialist
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
"""
  },

  "astra4": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Happy Holidays!

I'm Kent Rivera, Client Success Coordinator of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Kent Rivera
Client Success Coordinator
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
"""
  },

  "astra5": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Happy Holidays!

I'm Zach King, Web & Trailer Specialist of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Zach King
Web & Trailer Specialist
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
"""
    },

     "astra6": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Happy Holidays!

I'm Alex Carter, Marketing Team Lead of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Alex Carter
Marketing Team Lead
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
"""
    },

       "astra7": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

Happy Holidays!

I'm Megan, Production Coordinator of Astra Productions. We create 30-60 second cinematic book trailers and focused author websites that move readers from "interesting" to "click buy."

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links (one link you can share anywhere). If you already have a website, we can add the trailer and layout to it. If you don't, we can build the site for you.

Pricing: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you're open to it, reply with your book link (or title + synopsis), and I'll send back trailer hook concepts + a one-page site outline. If you'd like, I can also include 2-3 recent trailers and a sample author page so you can see the quality and style before deciding.

Best regards,
Megan
Production Coordinator
United States

If you'd prefer I don't follow up, click: {UnsubMailto}
(or just reply "unsubscribe").
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


def single_line(text: str) -> str:
    return " ".join((text or "").split())


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


def resolve_map_path(base: Path, value: str) -> Path:
    p = Path((value or "").strip())
    if not p:
        return p
    if not p.is_absolute():
        p = base / p
    return p


def load_account_map(map_path: Path) -> List[Tuple[Path, Path]]:
    if not map_path.exists():
        return []
    out: List[Tuple[Path, Path]] = []
    with map_path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items() if k}
            rec = row.get("recipientscsv") or row.get("recipients") or row.get("recipients_csv")
            log = row.get("logcsv") or row.get("log") or row.get("log_csv")
            if not rec or not log:
                continue
            out.append((resolve_map_path(map_path.parent, rec), resolve_map_path(map_path.parent, log)))
    return out


def load_done_from_logs(paths: List[Path]) -> Set[str]:
    out: Set[str] = set()
    for p in paths:
        out |= load_already_done(p)
    return out


def fmt_ts(dt: Optional[datetime]) -> str:
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


def rolling_24h_stats(log_path: Path, my_domains: Set[str], now: datetime) -> Dict[str, object]:
    cutoff = now - timedelta(hours=24)
    sent_times: List[datetime] = []
    ext_last: Dict[str, datetime] = {}

    if not log_path.exists():
        return {
            "messages": 0,
            "unique_external": 0,
            "unique_external_set": set(),
            "resume_messages": None,
            "resume_unique_external": None,
        }

    with log_path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("Status") or "").strip().upper() != "SENT":
                continue
            t = parse_ts(r.get("TimestampUTC") or "")
            if not t or t < cutoff:
                continue
            sent_times.append(t)
            email_addr = norm_email(r.get("Email") or "")
            if is_external(email_addr, my_domains):
                prev = ext_last.get(email_addr)
                if prev is None or t > prev:
                    ext_last[email_addr] = t

    sent_times.sort()
    resume_messages = (sent_times[0] + timedelta(hours=24)) if sent_times else None
    resume_unique_external = (min(ext_last.values()) + timedelta(hours=24)) if ext_last else None

    return {
        "messages": len(sent_times),
        "unique_external": len(ext_last),
        "unique_external_set": set(ext_last.keys()),
        "resume_messages": resume_messages,
        "resume_unique_external": resume_unique_external,
    }


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


def render_message_parts(
    author: str,
    book_title: str,
    subject: str,
    body_template: str,
    unsub_email: str,
    signature_file: Optional[Path],
) -> Tuple[str, str, str, Optional[str]]:
    unsub_mailto = make_unsub_mailto(unsub_email)

    author = (author or "there").strip()
    book_title = (book_title or "").strip() or "your book"

    format_args = {
        "AuthorName": author,
        "BookTitle": book_title,
        "UnsubEmail": unsub_email,
        "UnsubMailto": unsub_mailto,
        "SIGIMG": "{SIGIMG}",   # keep marker for HTML rendering
    }

    body_text = body_template.format(**format_args)
    subject_text = subject.format(
        AuthorName=author,
        BookTitle=book_title,
        UnsubEmail=unsub_email,
        UnsubMailto=unsub_mailto,
        SIGIMG="",
    )

    cid = SIGNATURE_CID if (signature_file and signature_file.exists()) else None
    html_body = text_to_html(body_text, unsub_mailto, cid=cid)
    return subject_text, body_text, html_body, cid


def build_message(
    from_email: str,
    to_email: str,
    author: str,
    book_title: str,
    subject: str,
    body_template: str,
    unsub_email: str,
    signature_file: Optional[Path] = None,
) -> Tuple[EmailMessage, str, str, str, Optional[str]]:
    subject_text, body_text, html_body, cid = render_message_parts(
        author,
        book_title,
        subject,
        body_template,
        unsub_email,
        signature_file,
    )

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject_text
    msg["Reply-To"] = from_email
    msg["List-Unsubscribe"] = f"<mailto:{unsub_email}?subject=unsubscribe>"

    # Plain text: remove marker so recipients don't see "{SIGIMG}"
    msg.set_content(body_text.replace("{SIGIMG}", "").strip())

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

    return msg, subject_text, body_text, html_body, cid


def send_via_sendgrid(
    api_key: str,
    from_email: str,
    to_email: str,
    reply_to: str,
    subject_text: str,
    body_text: str,
    html_body: str,
    unsub_email: str,
    signature_file: Optional[Path],
    cid: Optional[str],
) -> None:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail,
            Content,
            ReplyTo,
            Attachment,
            FileContent,
            FileName,
            FileType,
            Disposition,
            ContentId,
            Header,
        )
    except Exception as exc:
        raise RuntimeError(
            "sendgrid library not installed; add 'sendgrid' to requirements and install it"
        ) from exc

    mail = Mail(from_email=from_email, to_emails=to_email, subject=subject_text)
    mail.add_content(Content("text/plain", body_text.replace("{SIGIMG}", "").strip()))
    mail.add_content(Content("text/html", html_body))
    mail.reply_to = ReplyTo(reply_to)
    mail.add_header(Header("List-Unsubscribe", f"<mailto:{unsub_email}?subject=unsubscribe>"))

    if cid and signature_file and signature_file.exists() and "{SIGIMG}" in body_text:
        img_bytes = signature_file.read_bytes()
        encoded = base64.b64encode(img_bytes).decode("ascii")
        mail.add_attachment(
            Attachment(
                FileContent(encoded),
                FileName(signature_file.name),
                FileType("image/png"),
                Disposition("inline"),
                ContentId(cid),
            )
        )

    response = SendGridAPIClient(api_key).send(mail)
    if response.status_code != 202:
        body = response.body
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        raise RuntimeError(f"sendgrid_error: status={response.status_code} body={body}")

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
    profile_parser = argparse.ArgumentParser(add_help=False)
    profile_parser.add_argument("--profile", choices=sorted(PROFILES.keys()), help="Load a preset configuration.")
    profile_parser.add_argument("--list_profiles", action="store_true", help="List available profiles.")

    pre_args, _ = profile_parser.parse_known_args()
    if pre_args.list_profiles and not pre_args.profile:
        print("Profiles available:")
        for name in sorted(PROFILES.keys()):
            print(f" - {name}")
        return
    profile_defaults = PROFILES.get(pre_args.profile or "", {})

    ap = argparse.ArgumentParser(parents=[profile_parser])
    ap.add_argument("--csv")
    ap.add_argument("--log")
    ap.add_argument("--pitch", choices=sorted(PITCHES.keys()))
    ap.add_argument("--provider", choices=["private", "gmail", "sendgrid"], default="")
    ap.add_argument("--sendgrid", action="store_true", help="Use SendGrid Email API backend.")

    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--unsub", default=DEFAULT_UNSUB_EMAIL)
    ap.add_argument("--unsub_csv", default=str(DEFAULT_UNSUB_CSV))
    ap.add_argument("--suppress_csv", default=str(DEFAULT_SUPPRESS_CSV))
    ap.add_argument("--my_domains", default=DEFAULT_DOMAIN)

    ap.add_argument("--max_unique_external_24h", type=int, default=None)
    ap.add_argument("--max_messages_24h", type=int, default=None)

    ap.add_argument("--max_per_run", type=int, default=0)
    ap.add_argument("--repeat", action="store_true")
    ap.add_argument("--batch_size", type=int, default=10)
    ap.add_argument("--cooldown_seconds", type=int, default=0)
    ap.add_argument("--max_total", type=int, default=0)
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--preflight", action="store_true")

    ap.add_argument("--max_messages_1h", type=int, default=None)
    ap.add_argument("--domain_log", default="")
    ap.add_argument("--suppress_invalid", action="store_true")
    ap.add_argument("--from_email", "--from", dest="from_email", default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--password_env", default="")
    ap.add_argument("--account_map", default="account_map.csv")
    ap.add_argument("--global_dedupe", action="store_true")
    ap.add_argument("--global_dedupe_logs_pattern", default="*_log.csv")
    ap.add_argument("--global_dedupe_recipients_pattern", default="recipients_*.csv")

    if profile_defaults:
        ap.set_defaults(**profile_defaults)

    args = ap.parse_args()
    if args.list_profiles:
        print("Profiles available:")
        for name, cfg in sorted(PROFILES.items()):
            print(f" - {name}")
            for k, v in sorted(cfg.items()):
                print(f"    {k}: {v}")
        return
    if args.profile:
        print(f"PROFILE: {args.profile}")

    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    if args.sendgrid:
        if args.provider and args.provider != "sendgrid":
            print("ERROR: --sendgrid cannot be combined with --provider that is not sendgrid.")
            return
        args.provider = "sendgrid"
    if not args.provider and sendgrid_api_key:
        args.provider = "sendgrid"

    required_missing = [name for name, val in [
        ("provider", args.provider),
        ("csv", args.csv),
        ("log", args.log),
        ("pitch", args.pitch),
    ] if not val]
    if required_missing:
        print("ERROR missing required args:", ", ".join(required_missing))
        print("Provide them via flags or set a --profile that includes them.")
        return

    if args.provider == "sendgrid" and not args.dry_run and not sendgrid_api_key:
        print("ERROR: SENDGRID_API_KEY is required for --provider sendgrid.")
        return

    provider_defaults = PROVIDER_LIMIT_DEFAULTS.get(args.provider, {})
    if args.provider == "private" and args.max_messages_1h is None:
        args.max_messages_1h = int(provider_defaults.get("max_messages_1h", 0))
    if args.provider == "gmail":
        if args.max_messages_24h is None:
            args.max_messages_24h = int(provider_defaults.get("max_messages_24h", 0))
        if args.max_unique_external_24h is None:
            args.max_unique_external_24h = int(provider_defaults.get("max_unique_external_24h", 0))

    host, port = SMTP_PRESETS.get(args.provider, ("sendgrid", "api"))
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

    global_done: Set[str] = set()
    other_recipients: Set[str] = set()
    if args.global_dedupe:
        map_entries = load_account_map(Path(args.account_map))
        if map_entries:
            log_paths = [log_p for _, log_p in map_entries]
            recipient_paths = [rec_p for rec_p, _ in map_entries]
        else:
            base_dir = csv_path.parent
            log_paths = sorted(base_dir.glob(args.global_dedupe_logs_pattern))
            recipient_paths = sorted(base_dir.glob(args.global_dedupe_recipients_pattern))

        global_done = load_done_from_logs(log_paths)

        current_csv = csv_path.resolve()
        for p in recipient_paths:
            if p.resolve() == current_csv:
                continue
            other_recipients |= load_emails_from_csv(p)

    pending: List[Dict[str, str]] = []
    seen_in_input: Set[str] = set()
    skipped_dupes = 0
    skipped_global_logs = 0
    skipped_global_recipients = 0
    for r in rows:
        email_addr = norm_email(r.get("Email") or "")
        if not email_addr:
            continue
        if email_addr in seen_in_input:
            skipped_dupes += 1
            continue
        seen_in_input.add(email_addr)
        if email_addr in already_done or email_addr in unsubbed or email_addr in suppressed:
            continue
        if args.global_dedupe and email_addr in global_done:
            skipped_global_logs += 1
            continue
        if args.global_dedupe and email_addr in other_recipients:
            skipped_global_recipients += 1
            continue
        pending.append(r)

    print(f"RUN: provider={args.provider} host={host}:{port} pitch={args.pitch}")
    print(f"FILES: csv={csv_path.name} log={log_path.name} pending={len(pending)} interval={args.interval}s")
    if args.global_dedupe:
        print(
            "GLOBAL DEDUPE:"
            f" logs={len(global_done)} | other_recipients={len(other_recipients)} |"
            f" skipped_logs={skipped_global_logs} | skipped_recipients={skipped_global_recipients}"
        )
    if skipped_dupes:
        print(f"CSV DUPES: skipped={skipped_dupes}")
    if args.dry_run:
        print("DRY RUN: no emails will be sent.")
    if not pending:
        print("Nothing to send.")
        return

    domain_log_path = Path(args.domain_log) if args.domain_log else log_path
    if args.provider == "private" and args.max_messages_1h:
        print(f"PRIVATE 1H CAP: {args.max_messages_1h} (domain_log={domain_log_path.name})")
    if args.provider == "gmail" and (args.max_messages_24h or args.max_unique_external_24h):
        print(
            "GMAIL LIMITS:"
            f" max_messages_24h={args.max_messages_24h or 'off'}"
            f" max_unique_external_24h={args.max_unique_external_24h or 'off'}"
        )

    gmail_messages_24h = 0
    gmail_unique_ext: Set[str] = set()
    gmail_resume_messages: Optional[datetime] = None
    gmail_resume_unique: Optional[datetime] = None
    if args.provider == "gmail" and (args.max_messages_24h or args.max_unique_external_24h):
        now = datetime.now(timezone.utc)
        stats = rolling_24h_stats(log_path, my_domains, now)
        gmail_messages_24h = int(stats["messages"])
        gmail_unique_ext = set(stats["unique_external_set"])
        gmail_resume_messages = stats["resume_messages"]
        gmail_resume_unique = stats["resume_unique_external"]
        print(f"GMAIL 24H: messages={gmail_messages_24h} unique_external={len(gmail_unique_ext)}")

        if args.max_messages_24h and gmail_messages_24h >= args.max_messages_24h:
            print(
                "STOP: max_messages_24h reached. "
                f"Resume: {fmt_ts(gmail_resume_messages)} | remaining: {remaining_str(gmail_resume_messages)}"
            )
            return
        if args.max_unique_external_24h and len(gmail_unique_ext) >= args.max_unique_external_24h:
            print(
                "STOP: max_unique_external_24h reached. "
                f"Resume: {fmt_ts(gmail_resume_unique)} | remaining: {remaining_str(gmail_resume_unique)}"
            )
            return

    if args.preflight:
        if args.provider == "private" and args.max_messages_1h:
            print(f"DOMAIN LOG: {domain_log_path.name} | cap_1h={args.max_messages_1h}")
        print("PREFLIGHT: ok (no sending).")
        return

    from_user = norm_email(args.from_email) or norm_email(input("From (email address you are logging in as): "))
    pw = ""
    if not args.dry_run and args.provider != "sendgrid":
        if args.password_env:
            pw = os.environ.get(args.password_env, "").strip()
        if not pw and args.password:
            pw = args.password.strip()
        if not pw:
            pw = getpass("Password (Gmail uses App Password): ").strip()
    unsub_email = norm_email(args.unsub) or from_user

    # Choose signature file:
    # - only applies if the pitch body contains {SIGIMG}
    pitch_key = args.pitch
    sig_name = (SIGNATURE_BY_PITCH.get(pitch_key) or SIGNATURE_BY_FROM.get(from_user) or "")
    sig_name = sig_name.strip()
    sig_path = Path(sig_name) if (sig_name and "{SIGIMG}" in body_template) else None

    smtp: Optional[smtplib.SMTP] = None
    sent_this_run = 0
    invalid_count = 0
    error_count = 0
    repeat_mode = args.repeat
    cooldown_seconds = max(0, int(args.cooldown_seconds))
    batch_size = max(0, int(args.batch_size))
    if repeat_mode and batch_size <= 0:
        print("ERROR: --batch_size must be > 0 when --repeat is set.")
        return

    def ensure_smtp() -> smtplib.SMTP:
        nonlocal smtp
        if smtp is None:
            smtp = smtp_login(host, port, from_user, pw)
        return smtp

    def send_one(
        msg: EmailMessage,
        to_email: str,
        subject_text: str,
        body_text: str,
        html_body: str,
        cid: Optional[str],
    ) -> None:
        """
        PrivateEmail: connect per message (reduces DISCONNECTED loops)
        Gmail: keep connection open
        """
        nonlocal smtp
        if args.provider == "sendgrid":
            send_via_sendgrid(
                sendgrid_api_key,
                from_user,
                to_email,
                from_user,
                subject_text,
                body_text,
                html_body,
                unsub_email,
                sig_path,
                cid,
            )
            return
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

        pending_index = 0
        while True:
            if repeat_mode:
                if args.max_total and sent_this_run >= args.max_total:
                    print(f"STOP: reached --max_total={args.max_total}")
                    break
                if args.max_per_run and sent_this_run >= args.max_per_run:
                    print(f"STOP: reached --max_per_run={args.max_per_run}")
                    break

                batch_limit = batch_size
                if args.max_per_run:
                    batch_limit = min(batch_limit, args.max_per_run)
                if args.max_total:
                    batch_limit = min(batch_limit, max(0, args.max_total - sent_this_run))
                if batch_limit <= 0:
                    break
            else:
                batch_limit = len(pending)

            batch_sent = 0
            stop_reason = None
            next_index = pending_index

            for idx in range(pending_index, len(pending)):
                i = idx + 1
                r = pending[idx]
                to_email = norm_email(r.get("Email") or "")
                if not to_email:
                    next_index = idx + 1
                    continue

                if args.provider == "gmail" and (args.max_messages_24h or args.max_unique_external_24h):
                    if args.max_messages_24h and gmail_messages_24h >= args.max_messages_24h:
                        print(
                            "STOP: max_messages_24h reached. "
                            f"Resume: {fmt_ts(gmail_resume_messages)} | remaining: {remaining_str(gmail_resume_messages)}"
                        )
                        stop_reason = "max_messages_24h"
                        break
                    if (
                        args.max_unique_external_24h
                        and is_external(to_email, my_domains)
                        and to_email not in gmail_unique_ext
                        and len(gmail_unique_ext) >= args.max_unique_external_24h
                    ):
                        print(
                            "STOP: max_unique_external_24h reached. "
                            f"Resume: {fmt_ts(gmail_resume_unique)} | remaining: {remaining_str(gmail_resume_unique)}"
                        )
                        stop_reason = "max_unique_external_24h"
                        break

                if args.max_per_run and sent_this_run >= args.max_per_run:
                    print(f"STOP: reached --max_per_run={args.max_per_run}")
                    stop_reason = "max_per_run"
                    break

                if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                    print(f"STOP: reached --max_total={args.max_total}")
                    stop_reason = "max_total"
                    break

                author = (r.get("AuthorName") or "there").strip()
                book_title = (r.get("BookTitle") or r.get("Title") or "").strip()

                msg, subject_text, body_text, html_body, cid = build_message(
                    from_user, to_email, author, book_title,
                    subject, body_template, unsub_email,
                    signature_file=sig_path
                )

                next_index = idx + 1
                try:
                    if args.dry_run:
                        log_row(log_path, to_email, "DRYRUN", "not_sent")
                        print(f"[{i}/{len(pending)}] DRYRUN {to_email}")
                    else:
                        if args.provider == "private" and args.max_messages_1h:
                            domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                        send_one(msg, to_email, subject_text, body_text, html_body, cid)

                        log_row(log_path, to_email, "SENT")
                        print(f"[{i}/{len(pending)}] SENT {to_email}")
                        sent_this_run += 1
                        batch_sent += 1
                        if args.provider == "gmail":
                            gmail_messages_24h += 1
                            if is_external(to_email, my_domains):
                                gmail_unique_ext.add(to_email)

                        if args.provider == "private" and args.max_messages_1h and domain_log_path != log_path:
                            log_row(domain_log_path, to_email, "SENT")

                        if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                            print(f"STOP: reached --max_total={args.max_total}")
                            stop_reason = "max_total"

                except smtplib.SMTPRecipientsRefused as e:
                    rec = e.recipients.get(to_email) or next(iter(e.recipients.values()), None)
                    if rec:
                        code = rec[0]
                        text = _decode_smtp_err(rec[1])
                        cls = classify_smtp(int(code) if code is not None else None, text)

                        if cls == "BAD_RECIPIENT":
                            log_row(log_path, to_email, "INVALID", f"{code} {text}")
                            invalid_count += 1
                            print(f"[{i}/{len(pending)}] INVALID {to_email} :: {single_line(f'{code} {text}')}")
                            if args.suppress_invalid:
                                append_suppressed_email(suppress_csv_path, to_email)
                            continue

                        log_row(log_path, to_email, "ERROR", f"{code} {text}")
                        error_count += 1
                        print(f"[{i}/{len(pending)}] RECIPIENT ERROR {to_email} :: {single_line(f'{code} {text}')}")
                        continue

                    log_row(log_path, to_email, "ERROR", str(e))
                    error_count += 1
                    print(f"[{i}/{len(pending)}] RECIPIENT ERROR {to_email} :: {single_line(str(e))}")
                    continue

                except smtplib.SMTPAuthenticationError as e:
                    log_row(log_path, to_email, "ERROR", f"auth_failed: {e}")
                    error_count += 1
                    print(f"[{i}/{len(pending)}] AUTH ERROR (stop) {to_email} :: {single_line(str(e))}")
                    stop_reason = "auth_error"
                    break

                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPHeloError) as e:
                    log_row(log_path, to_email, "ERROR", f"disconnected: {e}")
                    error_count += 1
                    print(f"[{i}/{len(pending)}] DISCONNECTED {to_email} :: reconnecting and retrying once")

                    smtp_close(smtp)
                    smtp = None
                    sleep_with_jitter(max(args.interval, 60), jitter=10)

                    try:
                        if args.provider == "private" and args.max_messages_1h:
                            domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                        send_one(msg, to_email, subject_text, body_text, html_body, cid)

                        log_row(log_path, to_email, "SENT", "reconnect_ok")
                        print(f"[{i}/{len(pending)}] SENT (reconnect) {to_email}")
                        sent_this_run += 1
                        batch_sent += 1
                        if args.provider == "gmail":
                            gmail_messages_24h += 1
                            if is_external(to_email, my_domains):
                                gmail_unique_ext.add(to_email)

                        if args.provider == "private" and args.max_messages_1h and domain_log_path != log_path:
                            log_row(domain_log_path, to_email, "SENT")

                        if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                            print(f"STOP: reached --max_total={args.max_total}")
                            stop_reason = "max_total"

                    except Exception as e2:
                        code2, text2 = extract_code_text_from_exception(e2)
                        log_row(log_path, to_email, "ERROR", f"reconnect_failed: {code2} {text2}")
                        error_count += 1
                        print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{code2} {text2}')}")
                        stop_reason = "reconnect_failed"
                        break

                except (smtplib.SMTPDataError, smtplib.SMTPResponseException) as e:
                    code, text = extract_code_text_from_exception(e)
                    cls = classify_smtp(code, text)

                    if cls == "BAD_RECIPIENT":
                        log_row(log_path, to_email, "INVALID", f"{code} {text}")
                        invalid_count += 1
                        print(f"[{i}/{len(pending)}] INVALID {to_email} :: {single_line(f'{code} {text}')}")
                        if args.suppress_invalid:
                            append_suppressed_email(suppress_csv_path, to_email)
                        continue

                    if cls == "TEMP_THROTTLE":
                        log_row(log_path, to_email, "ERROR", f"{code} {text}")
                        wait_s = backoff_seconds()
                        error_count += 1
                        print(f"[{i}/{len(pending)}] THROTTLED {to_email} :: backoff {wait_s}s then retry")

                        time.sleep(wait_s)
                        smtp_close(smtp)
                        smtp = None
                        sleep_with_jitter(max(args.interval, 60), jitter=10)

                        try:
                            if args.provider == "private" and args.max_messages_1h:
                                domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                            send_one(msg, to_email, subject_text, body_text, html_body, cid)

                            log_row(log_path, to_email, "SENT", "throttle_retry_ok")
                            print(f"[{i}/{len(pending)}] SENT (retry) {to_email}")
                            sent_this_run += 1
                            batch_sent += 1
                            if args.provider == "gmail":
                                gmail_messages_24h += 1
                                if is_external(to_email, my_domains):
                                    gmail_unique_ext.add(to_email)

                            if args.provider == "private" and args.max_messages_1h and domain_log_path != log_path:
                                log_row(domain_log_path, to_email, "SENT")

                            if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                                print(f"STOP: reached --max_total={args.max_total}")
                                stop_reason = "max_total"
                                break
                            if repeat_mode and batch_sent >= batch_limit:
                                break
                            continue
                        except Exception as e2:
                            code2, text2 = extract_code_text_from_exception(e2)
                            log_row(log_path, to_email, "ERROR", f"retry_failed: {code2} {text2}")
                            error_count += 1
                            print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{code2} {text2}')}")
                            stop_reason = "retry_failed"
                            break

                    log_row(log_path, to_email, "ERROR", f"{code} {text}")
                    error_count += 1
                    print(f"[{i}/{len(pending)}] ERROR {to_email} :: {single_line(f'{code} {text}')}")

                except Exception as e:
                    log_row(log_path, to_email, "ERROR", str(e))
                    error_count += 1
                    print(f"[{i}/{len(pending)}] ERROR {to_email} :: {single_line(str(e))}")

                if stop_reason:
                    break
                if repeat_mode and batch_sent >= batch_limit:
                    break
                if idx < len(pending) - 1:
                    sleep_with_jitter(args.interval, jitter=10)

            pending_index = next_index

            if repeat_mode:
                remaining_pending = max(0, len(pending) - pending_index)
                if args.max_total > 0:
                    remaining_allowed = max(0, args.max_total - sent_this_run)
                    remaining_estimate = min(remaining_pending, remaining_allowed)
                else:
                    remaining_estimate = remaining_pending

                next_sleep_seconds = 0
                if (
                    not stop_reason
                    and pending_index < len(pending)
                    and not (args.max_total and sent_this_run >= args.max_total)
                    and not (args.max_per_run and sent_this_run >= args.max_per_run)
                ):
                    next_sleep_seconds = cooldown_seconds

                print(
                    f"BATCH: sent={batch_sent} total={sent_this_run} "
                    f"remaining_estimate={remaining_estimate} next_sleep_seconds={next_sleep_seconds}"
                )

                if (
                    stop_reason
                    or pending_index >= len(pending)
                    or (args.max_total and sent_this_run >= args.max_total)
                    or (args.max_per_run and sent_this_run >= args.max_per_run)
                ):
                    break

                if cooldown_seconds > 0:
                    time.sleep(cooldown_seconds)
            else:
                break

        print(f"DONE: sent={sent_this_run} invalid={invalid_count} errors={error_count}")

    finally:
        smtp_close(smtp)

if __name__ == "__main__":
    main()
