import argparse
import csv
import html
import ssl
import smtplib
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from getpass import getpass
from pathlib import Path
from typing import Optional, Tuple, Set, Dict, List, Deque
from urllib.parse import quote

# ===== SMTP PRESETS =====
SMTP_PRESETS = {
    "private": ("mail.privateemail.com", 587),  # Namecheap PrivateEmail
    "gmail":   ("smtp.gmail.com", 587),         # Gmail / Google Workspace
}

DEFAULT_DOMAIN = "barnesnobleinfo.com"
DEFAULT_UNSUB_EMAIL = f"unsubscribe@{DEFAULT_DOMAIN}"
DEFAULT_UNSUB_CSV = Path("unsubscribed.csv")  # optional, header: Email

# ===== 5 SUBJECTS + 5 BODIES (NO {UnsubMailto} INSIDE) =====
PITCHES = {
    "pitch1": {
        "subject": "Barnes & Noble Physical Placement",
        "body": """Dear {AuthorName},

My name is Annette Danek-Akey, Chief Supply Chain Officer, and I oversee all operations for the Barnes & Noble Distribution Centers. I help authors place their books on consignment in B&N physical bookstores across the United States.

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
Annette Danek-Akey
Chief Supply Chain Officer
Barnes & Noble 

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
    "subject": "Quick Idea to make your book stand out online",
    "body": """Hi {AuthorName},

My name is Sofia Madel, and I handle email marketing at Barnes & Noble, Inc. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Best regards,

Sofia Madel, Email Marketing Specialist
Barnes & Noble Inc.
United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "gmail2": {
    "subject": "Little, Brown - Hachette Book Group Traditional Publishing Proposal",
    "body": """Hi {AuthorName},

My name is Sally Kim, and I am the Acquisition Director and Publisher at Little, Brown - Hachette Book Group. I am pleased to inform you that we have selected your book for consideration for traditional publishing.

In my role, I focus on identifying exceptional books and story-based projects and positioning them for serious publishing. I have extensive experience in packaging and presenting strong intellectual property in a format that resonates with decision-makers, including clear positioning, concise narratives, and evidence of market response.

I am reaching out because your work stands out to us, and we would like to explore it for traditional publishing. Additionally, if it aligns with our vision, we could consider adapting it for film or television.
I understand that the publishing process can sometimes be daunting. However, with the right package and next steps, we can significantly enhance our discussions.

Before we move forward, I would love to learn more about your marketing efforts so far. Even small successes are valuable! What promotional activities have you undertaken? This could include ads, social media content, public relations, newsletters, events, awards, influencer outreach, or podcast/radio/TV appearances, and what has performed best for you?

If you are open to discussing next steps, please send me the following materials (drafts are perfectly acceptable):

1. Author website/landing page (link)

2. Book trailer (link/file), reviews/endorsements (from Barnes & Noble, Amazon, Goodreads, editorial quotes, and any press)

3. Participation in festivals/book fairs (photos, programs, certificates)

4. Screenplay (if available) — or a logline along with a one-page synopsis (optional)

5. Treatment/pitch deck for film/TV adaptation

6. Interviews/features (links to radio/TV/podcasts/blogs)

Additionally, please provide your book's basic information, including genre, publication date, word count, and whether the rights are available.

Once I receive your materials and details, I will come back to you with a clear submission angle and a priority list.

Looking forward to your response.

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

My name is Josefina Stenstrom, and I handle email marketing at Barnes & Noble, Inc. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Best regards,

Josefina Stenstrom
Email Marketing Specialist
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
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

I’m Sofia Margaret, Creative Producer of Astra Productions. We create 30–60 second cinematic book trailers and focused author websites that move readers from “interesting” to “click buy.”

The website complements the trailer: it gives the trailer a clean, distraction-free home with your cover, hook, best reviews, and direct purchase links. If you already have a website, we can add the trailer + a simple landing page to it. If you don’t, we can build the site for you.

If it looks like a fit, pricing is: Trailer US$999 | Website US$499 | Bundle US$1,299.

If you’re open to it, reply with your book link (or title + synopsis), I’ll send back trailer hook concepts + a one-page site outline.

Portfolio: https://astra-productions.oneapp.dev/

 Best regards,
 Sofia Margaret, Creative Producer
 Astra Productions
 United States

If you’d prefer I don’t follow up, click: {UnsubMailto}
(or just reply “unsubscribe”).
"""
  },

  "astra2": {
    "subject": "Quick Idea to make your Book stand out online",
    "body": """Hi {AuthorName},

    I’m Windelle JC, CEO of Astra Productions. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Portfolio: https://astra-productions.oneapp.dev/

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

I’m Jordan Miller, Author Outreach Specialist of Astra Productions. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Portfolio: https://astra-productions.oneapp.dev/

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

    I’m Kent Carvajal, Client Success Coordinator of Astra Productions. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Portfolio: https://astra-productions.oneapp.dev/

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

I’m Zach King, Web & Trailer Specialist of Astra Productions. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Portfolio: https://astra-productions.oneapp.dev/

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

I’m Alex Carter, Marketing Team Lead of Astra Productions. We help authors turn that first glance into a movie-preview moment—then guide viewers straight to the buy link. 
You didn’t write your book to be judged by a thumbnail and a two-line blurb. But online, that’s exactly what happens—readers decide fast, and strong books get skipped simply because the first impression doesn’t land.

I’m reaching out because your work stands out to us—the kind of storytelling that’s easy to picture as scenes, not just words.

What we create (done-for-you):
Cinematic book trailer (45–60 seconds)
Clean author page (trailer + books + about + buy/contact in one place)
We publish the trailer to YouTube + Facebook so you have ready-to-share assets for launch and ads.

Investment:
US$999 for a trailer
US$499 for a website
US$1,299 bundle for both

For context: some professional studios list book-trailer pricing starting around US$3,000+ (and higher-end cinematic/live-action productions can run far above that depending on scope).

If you reply with your book link (or title + synopsis), I’ll send back two trailer hook concepts + a one-page site outline.

Portfolio: https://astra-productions.oneapp.dev/

Best regards,
Alex Carter, Marketing Team Lead
Astra Productions
United States

Opt out: {UnsubMailto}
(or just reply “unsubscribe”).
"""
    },

       "astra7": {
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
    return ("@" in addr) and (addr.split("@", 1)[1] not in my_domains)

def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows: List[Dict[str, str]] = []
        for r in csv.DictReader(f):
            rows.append({(k or "").strip().lstrip("\ufeff"): (v or "").strip() for k, v in r.items()})
        return rows

def load_sent_only(sent_log: Path) -> Set[str]:
    if not sent_log.exists():
        return set()
    out: Set[str] = set()
    with sent_log.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("Status") or "").strip().upper() != "SENT":
                continue
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out

def load_unsubscribed(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    out: Set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
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

def text_to_html(body_text: str, unsub_mailto: str) -> str:
    safe = html.escape(body_text)
    safe = safe.replace(html.escape(unsub_mailto), f"<a href='{html.escape(unsub_mailto)}'>unsubscribe</a>")
    safe = safe.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<html><body><p>{safe}</p></body></html>"

def build_message(
    from_email: str,
    to_email: str,
    author: str,
    book_title: str,
    subject: str,
    body_template: str,
    unsub_email: str
) -> EmailMessage:
    unsub_mailto = make_unsub_mailto(unsub_email)

    author = (author or "there").strip()
    book_title = (book_title or "").strip()

    # fallback keys if your CSV uses a different header name
    if not book_title:
        book_title = "your book"

    body_text = body_template.format(
        AuthorName=author,
        BookTitle=book_title,
        UnsubEmail=unsub_email,
        UnsubMailto=unsub_mailto
    )

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    # replies go to the sender mailbox
    msg["Reply-To"] = from_email

    # unsubscribe goes to the sender mailbox too
    msg["List-Unsubscribe"] = f"<mailto:{unsub_email}?subject=unsubscribe>"

    msg.set_content(body_text)
    msg.add_alternative(text_to_html(body_text, unsub_mailto), subtype="html")
    return msg

def send_one(host: str, port: int, user: str, pw: str, msg: EmailMessage) -> None:
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        s.login(user, pw)
        s.send_message(msg)

def load_rolling_24h_state(
    sent_log: Path,
    my_domains: Set[str],
    now: datetime
) -> Tuple[Deque[datetime], Dict[str, datetime]]:
    cutoff = now - timedelta(hours=24)
    times: List[datetime] = []
    ext_last: Dict[str, datetime] = {}

    if not sent_log.exists():
        return deque(), ext_last

    with sent_log.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("Status") or "").strip().upper() != "SENT":
                continue

            t = parse_ts(r.get("TimestampUTC") or "")
            if not t or t < cutoff:
                continue

            times.append(t)

            email_addr = norm_email(r.get("Email") or "")
            if email_addr and is_external(email_addr, my_domains):
                prev = ext_last.get(email_addr)
                if prev is None or t > prev:
                    ext_last[email_addr] = t

    times.sort()
    return deque(times), ext_last

def prune_rolling_state(
    sent_times: Deque[datetime],
    ext_last: Dict[str, datetime],
    now: datetime
) -> None:
    cutoff = now - timedelta(hours=24)

    while sent_times and sent_times[0] < cutoff:
        sent_times.popleft()

    expired = [email for email, t in ext_last.items() if t < cutoff]
    for email in expired:
        ext_last.pop(email, None)

def earliest_resume_messages(sent_times: Deque[datetime]) -> Optional[datetime]:
    return (sent_times[0] + timedelta(hours=24)) if sent_times else None

def earliest_resume_unique_external(ext_last: Dict[str, datetime]) -> Optional[datetime]:
    if not ext_last:
        return None
    oldest = min(ext_last.values())
    return oldest + timedelta(hours=24)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--pitch", required=True, choices=sorted(PITCHES.keys()))
    ap.add_argument("--provider", choices=["private", "gmail"], required=True)

    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--unsub", default=DEFAULT_UNSUB_EMAIL)
    ap.add_argument("--unsub_csv", default=str(DEFAULT_UNSUB_CSV))

    ap.add_argument("--my_domains", default=DEFAULT_DOMAIN, help="Comma-separated domains considered internal")

    ap.add_argument("--max_unique_external_24h", type=int, default=1900, help="Safety buffer under Gmail cap")
    ap.add_argument("--max_messages_24h", type=int, default=1900, help="Safety buffer under Gmail cap")

    ap.add_argument("--max_per_run", type=int, default=0, help="0 = no cap")
    ap.add_argument("--dry_run", action="store_true")

    args = ap.parse_args()

    host, port = SMTP_PRESETS[args.provider]

    pitch = PITCHES[args.pitch]
    subject = (pitch.get("subject") or "").strip()
    body_template = (pitch.get("body") or "").strip()

    csv_path = Path(args.csv)
    log_path = Path(args.log)
    unsub_csv_path = Path(args.unsub_csv)

    if not csv_path.exists():
        print("ERROR missing:", csv_path)
        return

    my_domains = {d.strip().lower() for d in (args.my_domains or "").split(",") if d.strip()}
    if not my_domains:
        my_domains = {DEFAULT_DOMAIN}

    rows = read_rows(csv_path)
    sent = load_sent_only(log_path)
    unsubbed = load_unsubscribed(unsub_csv_path)

    pending: List[Dict[str, str]] = []
    for r in rows:
        email_addr = norm_email(r.get("Email") or "")
        if email_addr and email_addr not in sent and email_addr not in unsubbed:
            pending.append(r)

    print(f"PROVIDER: {args.provider} | HOST: {host}:{port}")
    print(f"PITCH: {args.pitch} | CSV: {csv_path.name} | Pending: {len(pending)} | Interval: {args.interval}s")
    if args.dry_run:
        print("DRY RUN: no emails will be sent.")
    if not pending:
        print("Nothing to send.")
        return

    from_user = norm_email(input("From (email address you are logging in as): ").strip())
    pw = getpass("Password (Gmail uses App Password): ").strip()

    # unsubscribe goes to the same mailbox that sent the email
    unsub_email = from_user

    sent_times: Deque[datetime] = deque()
    ext_last: Dict[str, datetime] = {}

    if args.provider == "gmail":
        now0 = datetime.now(timezone.utc)
        sent_times, ext_last = load_rolling_24h_state(log_path, my_domains, now0)
        prune_rolling_state(sent_times, ext_last, now0)
        print(f"LAST 24H (from log): messages_sent={len(sent_times)} | unique_external={len(ext_last)}")

    sent_this_run = 0

    for i, r in enumerate(pending, start=1):
        now = datetime.now(timezone.utc)

        if args.provider == "gmail":
            prune_rolling_state(sent_times, ext_last, now)
            if len(sent_times) >= args.max_messages_24h:
                print(f"STOP: near messages/24h limit (last24h_messages={len(sent_times)}).")
                resume = earliest_resume_messages(sent_times)
                if resume:
                    print(f"Estimated earliest resume (UTC): {resume.isoformat()}")
                break

        to_email = norm_email(r.get("Email") or "")
        if not to_email:
            continue

        if args.max_per_run and sent_this_run >= args.max_per_run:
            print(f"STOP: reached --max_per_run={args.max_per_run}")
            break

        if args.provider == "gmail" and is_external(to_email, my_domains):
            if to_email not in ext_last and len(ext_last) >= args.max_unique_external_24h:
                print(f"STOP: near unique-external/24h limit (last24h_unique_external={len(ext_last)}).")
                resume = earliest_resume_unique_external(ext_last)
                if resume:
                    print(f"Estimated earliest resume (UTC): {resume.isoformat()}")
                break

        author = (r.get("AuthorName") or "there").strip()

        # NEW: BookTitle from CSV (header: BookTitle)
        book_title = (r.get("BookTitle") or r.get("Title") or "").strip()

        msg = build_message(from_user, to_email, author, book_title, subject, body_template, unsub_email)

        try:
            if args.dry_run:
                log_row(log_path, to_email, "DRYRUN", "not_sent")
                print(f"[{i}/{len(pending)}] DRYRUN -> {to_email}")
            else:
                send_one(host, port, from_user, pw, msg)
                log_row(log_path, to_email, "SENT")
                print(f"[{i}/{len(pending)}] SENT -> {to_email}")

                sent_this_run += 1

                if args.provider == "gmail":
                    tnow = datetime.now(timezone.utc)
                    sent_times.append(tnow)
                    if is_external(to_email, my_domains):
                        ext_last[to_email] = tnow

        except smtplib.SMTPAuthenticationError as e:
            log_row(log_path, to_email, "ERROR", f"auth_failed: {e}")
            print(f"[{i}/{len(pending)}] AUTH ERROR (stop) -> {to_email} :: {e}")
            break

        except (smtplib.SMTPDataError, smtplib.SMTPResponseException) as e:
            code = getattr(e, "smtp_code", None)
            raw = getattr(e, "smtp_error", b"")
            text = raw.decode(errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)

            log_row(log_path, to_email, "ERROR", f"{code} {text}")
            print(f"[{i}/{len(pending)}] ERROR (stop) -> {to_email} :: {code} {text}")

            if args.provider == "gmail":
                now = datetime.now(timezone.utc)
                prune_rolling_state(sent_times, ext_last, now)

                def _fmt(dt: Optional[datetime]) -> str:
                    if not dt:
                        return "n/a"
                    manila = dt + timedelta(hours=8)
                    return f"{dt.isoformat()}Z | Manila: {manila.strftime('%Y-%m-%d %H:%M:%S')}"

                print(f"ROLLING 24H NOW: messages_sent={len(sent_times)} | unique_external={len(ext_last)}")
                print(f"Estimated resume (messages): {_fmt(earliest_resume_messages(sent_times))}")
                print(f"Estimated resume (unique external): {_fmt(earliest_resume_unique_external(ext_last))}")

            break

        except smtplib.SMTPRecipientsRefused as e:
            rec = e.recipients.get(to_email) or next(iter(e.recipients.values()), None)
            if rec:
                code, msg_bytes = rec[0], rec[1]
                msg_text = msg_bytes.decode(errors="ignore") if hasattr(msg_bytes, "decode") else str(msg_bytes)
                log_row(log_path, to_email, "ERROR", f"{code} {msg_text}")
                print(f"[{i}/{len(pending)}] RECIPIENT ERROR -> {to_email} :: {code} {msg_text}")
            else:
                log_row(log_path, to_email, "ERROR", str(e))
                print(f"[{i}/{len(pending)}] RECIPIENT ERROR -> {to_email} :: {e}")

        except Exception as e:
            log_row(log_path, to_email, "ERROR", str(e))
            print(f"[{i}/{len(pending)}] ERROR -> {to_email} :: {e}")

        if i < len(pending):
            time.sleep(args.interval)

    if args.provider == "gmail":
        now_end = datetime.now(timezone.utc)
        prune_rolling_state(sent_times, ext_last, now_end)
        print(f"END (rolling 24h): messages_sent={len(sent_times)} | unique_external={len(ext_last)}")

    print("Done.")

if __name__ == "__main__":
    main()
