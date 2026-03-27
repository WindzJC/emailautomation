from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard_core import (  # noqa: E402
    SendAttempt,
    canonical_event_status,
    canonical_message_id,
    extract_message_id_from_info,
    is_sendgrid_test_event,
    latest_send_profile_by_message_id,
    parse_log_timestamp,
    resolve_event_profile,
    send_attempts_by_email,
    unique_send_profile_by_email,
)
from send_shard import PROFILES  # noqa: E402
from sendgrid_hygiene import (  # noqa: E402
    compute_webhook_dedupe_key,
    domain_from_email,
    load_events_jsonl,
    load_suppression_records,
    parse_iso_utc,
    write_suppression_records,
)


REPORT_TZ_NAME = os.environ.get("DASHBOARD_TIMEZONE", "America/Los_Angeles").strip() or "America/Los_Angeles"
FAILURE_STATUSES = {"bounce", "blocked", "dropped", "spamreport"}
DELIVERED_LIKE_STATUSES = {"delivered", "open", "click", "unsubscribe", "group_unsubscribe"}
TERMINAL_STATUSES = FAILURE_STATUSES | DELIVERED_LIKE_STATUSES
DEFERRED_STATUSES = {"deferred"}
REASON_SNIPPET_LIMIT = 160

BOUNCE_CLASSIFICATION_MAP = {
    "invalid address": "mailbox_not_found",
    "mailbox not found": "mailbox_not_found",
    "recipient not found": "mailbox_not_found",
    "bad destination mailbox address": "mailbox_not_found",
    "mailbox unavailable": "mailbox_full",
    "mailbox full": "mailbox_full",
    "technical": "deferred_temp",
    "reputation": "reputation_block",
    "content": "policy_denied",
    "policy": "policy_denied",
    "frequency": "policy_denied",
    "volume": "policy_denied",
}

REASON_PATTERN_MAP = (
    ("senderscore", "reputation_block"),
    ("blocklist", "reputation_block"),
    ("dnsbl", "reputation_block"),
    ("found on one or more dnsbls", "reputation_block"),
    ("validity", "reputation_block"),
    ("reputation", "reputation_block"),
    ("not our customer", "mailbox_not_found"),
    ("account closed", "mailbox_disabled"),
    ("account inactive", "mailbox_disabled"),
    ("mailbox is disabled", "mailbox_disabled"),
    ("mailbox disabled", "mailbox_disabled"),
    ("disableduser", "mailbox_disabled"),
    ("inactive", "mailbox_disabled"),
    ("mailbox full", "mailbox_full"),
    ("out of storage space", "mailbox_full"),
    ("out of storage", "mailbox_full"),
    ("inbox is out of storage space", "mailbox_full"),
    ("over quota", "mailbox_full"),
    ("quota exceeded", "mailbox_full"),
    ("overquotatemp", "mailbox_full"),
    ("overquotaperm", "mailbox_full"),
    ("inode limit exceeded", "mailbox_full"),
    ("access denied", "policy_denied"),
    ("policy", "policy_denied"),
    ("connection refused", "policy_denied"),
    ("administrative prohibition", "policy_denied"),
    ("recipient rejected - elnk001_403", "policy_denied"),
    ("user unknown", "mailbox_not_found"),
    ("does not exist", "mailbox_not_found"),
    ("recipient not found", "mailbox_not_found"),
    ("mailbox not found", "mailbox_not_found"),
    ("recipient address rejected: user", "mailbox_not_found"),
    ("recipient rejected", "mailbox_not_found"),
    ("email address could not be found", "mailbox_not_found"),
    ("was misspelled", "invalid_recipient"),
    ("invalid recipient", "invalid_recipient"),
    ("bad recipient", "invalid_recipient"),
)


@dataclass
class AcceptedMessage:
    profile: str
    email: str
    domain: str
    from_email: str
    accepted_at_utc: datetime
    accepted_at_local: str
    message_id: str
    is_canary: bool
    source_log: str
    info: str
    events: List[Dict[str, str]] = field(default_factory=list)


def resolve_report_timezone(value: str = "") -> ZoneInfo:
    raw = (value or "").strip() or REPORT_TZ_NAME
    try:
        return ZoneInfo(raw)
    except Exception:
        return ZoneInfo("UTC")


def sendgrid_profiles(profile_configs: Optional[Dict[str, Dict[str, object]]] = None) -> List[str]:
    configs = profile_configs or PROFILES
    return [name for name, cfg in configs.items() if str(cfg.get("provider") or "") == "sendgrid"]


def _profile_lookup_by_from_email(profile_names: Iterable[str], profile_configs: Dict[str, Dict[str, object]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for profile in profile_names:
        from_email = str(profile_configs[profile].get("from_email") or "").strip().lower()
        if from_email:
            lookup[from_email] = profile
    return lookup


def _profile_lookup_by_shard(profile_names: Iterable[str], profile_configs: Dict[str, Dict[str, object]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for profile in profile_names:
        shard = Path(str(profile_configs[profile].get("csv") or "")).name.strip().lower()
        if shard:
            lookup[shard] = profile
    return lookup


def collect_send_attempts(root: Path, profile_configs: Dict[str, Dict[str, object]]) -> List[SendAttempt]:
    attempts: List[SendAttempt] = []
    for profile in sendgrid_profiles(profile_configs):
        log_path = root / str(profile_configs[profile]["log"])
        if not log_path.exists():
            continue
        with log_path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if (row.get("Status") or "").strip() != "SENT":
                    continue
                email = (row.get("Email") or "").strip().lower()
                ts = parse_log_timestamp(row.get("TimestampUTC", ""))
                if not email or not ts:
                    continue
                attempts.append(
                    SendAttempt(
                        profile=profile,
                        email=email,
                        timestamp=ts,
                        message_id=extract_message_id_from_info(row.get("Info", "")),
                    )
                )
    return attempts


def parse_window_args(args: argparse.Namespace, report_tz: ZoneInfo) -> Tuple[datetime, datetime, str]:
    if args.date:
        local_start = datetime.fromisoformat(args.date).replace(tzinfo=report_tz)
        local_end = local_start + timedelta(days=1)
        return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc), args.date
    since = parse_iso_utc(args.since or "")
    until = parse_iso_utc(args.until or "")
    if not since:
        raise SystemExit("Either --date or --since is required.")
    if not until:
        until = datetime.now(timezone.utc)
    if until <= since:
        raise SystemExit("--until must be later than --since.")
    label = since.astimezone(report_tz).strftime("%Y-%m-%d")
    return since, until, label


def load_accepted_messages(
    root: Path,
    start_utc: datetime,
    end_utc: datetime,
    report_tz: ZoneInfo,
    profile_configs: Dict[str, Dict[str, object]],
) -> List[AcceptedMessage]:
    messages: List[AcceptedMessage] = []
    for profile in sendgrid_profiles(profile_configs):
        cfg = profile_configs[profile]
        always_send = str(cfg.get("always_send") or "").strip().lower()
        from_email = str(cfg.get("from_email") or "").strip().lower()
        log_path = root / str(cfg["log"])
        if not log_path.exists():
            continue
        with log_path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if (row.get("Status") or "").strip() != "SENT":
                    continue
                ts = parse_log_timestamp(row.get("TimestampUTC", ""))
                if not ts or not (start_utc <= ts < end_utc):
                    continue
                email = (row.get("Email") or "").strip().lower()
                if not email:
                    continue
                messages.append(
                    AcceptedMessage(
                        profile=profile,
                        email=email,
                        domain=domain_from_email(email),
                        from_email=from_email,
                        accepted_at_utc=ts,
                        accepted_at_local=ts.astimezone(report_tz).strftime("%Y-%m-%d %H:%M:%S %Z"),
                        message_id=extract_message_id_from_info(row.get("Info", "")),
                        is_canary=email == always_send,
                        source_log=log_path.name,
                        info=(row.get("Info") or "").strip(),
                    )
                )
    messages.sort(key=lambda item: item.accepted_at_utc)
    return messages


def dedupe_events(events: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[str] = set()
    unique: List[Dict[str, str]] = []
    for event in events:
        key = (event.get("dedupe_key") or "").strip() or compute_webhook_dedupe_key(event)
        if key in seen:
            continue
        seen.add(key)
        event["dedupe_key"] = key
        unique.append(event)
    return unique


def _message_by_message_id(messages: Sequence[AcceptedMessage]) -> Dict[str, List[AcceptedMessage]]:
    grouped: Dict[str, List[AcceptedMessage]] = defaultdict(list)
    for message in messages:
        if message.message_id:
            grouped[message.message_id].append(message)
    return grouped


def _message_by_profile_email(messages: Sequence[AcceptedMessage]) -> Dict[Tuple[str, str], List[AcceptedMessage]]:
    grouped: Dict[Tuple[str, str], List[AcceptedMessage]] = defaultdict(list)
    for message in messages:
        grouped[(message.profile, message.email)].append(message)
    return grouped


def _pick_message_candidate(candidates: Sequence[AcceptedMessage], event_time: Optional[datetime], tolerance_seconds: int = 300) -> Optional[AcceptedMessage]:
    if not candidates:
        return None
    if event_time is None:
        return candidates[-1]
    threshold = event_time + timedelta(seconds=max(0, tolerance_seconds))
    for candidate in reversed(candidates):
        if candidate.accepted_at_utc <= threshold:
            return candidate
    return candidates[-1]


def attach_events_to_messages(
    root: Path,
    messages: Sequence[AcceptedMessage],
    events: Sequence[Dict[str, str]],
    profile_configs: Dict[str, Dict[str, object]],
) -> Dict[str, int]:
    profile_names = sendgrid_profiles(profile_configs)
    attempts = collect_send_attempts(root, profile_configs)
    email_to_profile = unique_send_profile_by_email(attempts)
    message_id_to_profile = latest_send_profile_by_message_id(attempts)
    from_email_to_profile = _profile_lookup_by_from_email(profile_names, profile_configs)
    shard_to_profile = _profile_lookup_by_shard(profile_names, profile_configs)
    attempts_for_email = send_attempts_by_email(attempts)
    by_message_id = _message_by_message_id(messages)
    by_profile_email = _message_by_profile_email(messages)

    attached = 0
    unmatched = 0
    for event in events:
        if is_sendgrid_test_event(event):
            continue
        profile, source = resolve_event_profile(
            event,
            email_to_profile,
            message_id_to_profile,
            from_email_to_profile,
            shard_to_profile,
            attempts_for_email,
        )
        if profile:
            event["profile"] = profile
        if source:
            event["attribution_source"] = source
        event_time = parse_iso_utc(event.get("processed_at_utc", "")) or parse_iso_utc(event.get("received_at_utc", ""))
        message_id = canonical_message_id(event.get("message_id", ""))
        candidate: Optional[AcceptedMessage] = None
        if message_id:
            candidate = _pick_message_candidate(by_message_id.get(message_id, []), event_time)
        if candidate is None:
            key = ((event.get("profile") or "").strip(), (event.get("email") or "").strip().lower())
            if key[0] and key[1]:
                candidate = _pick_message_candidate(by_profile_email.get(key, []), event_time)
        if candidate is None:
            unmatched += 1
            continue
        candidate.events.append(event)
        attached += 1
    return {"attached": attached, "unmatched": unmatched}


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def classify_failure(reason_text: str, smtp_code: str, event_type: str, bounce_classification: str = "") -> str:
    bounce_class = _normalize_text(bounce_classification)
    reason = (reason_text or "").lower()
    status = (event_type or "").lower()
    code = (smtp_code or "").strip()
    for token, category in BOUNCE_CLASSIFICATION_MAP.items():
        if token in bounce_class:
            return category
    if status == "spamreport":
        return "spam_report"
    if "disabled" in bounce_class:
        return "mailbox_disabled"
    if "invalid" in bounce_class and "address" in bounce_class:
        return "invalid_recipient"
    if status == "deferred":
        return "deferred_temp"
    for token, category in REASON_PATTERN_MAP:
        if token in reason:
            return category
    if "address rejected" in reason and "does not exist" not in reason:
        return "invalid_recipient"
    if "mailbox unavailable" in reason and (code.startswith("550") or "5.1.1" in reason or "5.5.0" in reason):
        return "mailbox_not_found"
    if status == "blocked" and code.startswith("5"):
        return "policy_denied"
    return "unknown"


def message_counts(message: AcceptedMessage) -> Counter:
    return Counter(canonical_event_status(event.get("status", "")) for event in message.events)


def message_outcome(message: AcceptedMessage) -> Dict[str, object]:
    counts = message_counts(message)
    statuses = {status for status in counts if status}
    has_failure = bool(statuses & FAILURE_STATUSES)
    has_delivered = bool(statuses & DELIVERED_LIKE_STATUSES)
    awaiting = not has_failure and not has_delivered
    if counts["spamreport"]:
        final_status = "spamreport"
    elif counts["bounce"]:
        final_status = "bounce"
    elif counts["dropped"]:
        final_status = "dropped"
    elif counts["blocked"]:
        final_status = "blocked"
    elif has_delivered:
        final_status = "delivered"
    elif counts["deferred"]:
        final_status = "deferred"
    elif counts["processed"]:
        final_status = "processed"
    else:
        final_status = "awaiting"

    failure_event = None
    for event in reversed(message.events):
        status = canonical_event_status(event.get("status", ""))
        if status in FAILURE_STATUSES:
            failure_event = event
            break
    failure_category = ""
    if failure_event:
        failure_category = classify_failure(
            failure_event.get("response", ""),
            failure_event.get("code", ""),
            canonical_event_status(failure_event.get("status", "")),
            failure_event.get("bounce_classification", ""),
        )
    return {
        "final_status": final_status,
        "awaiting": awaiting,
        "has_delivered": has_delivered,
        "has_failure": has_failure,
        "has_deferred": bool(counts["deferred"]) and awaiting,
        "open_unique": 1 if counts["open"] else 0,
        "open_total": counts["open"],
        "click_unique": 1 if counts["click"] else 0,
        "click_total": counts["click"],
        "failure_event": failure_event,
        "failure_category": failure_category,
    }


def build_profile_summary(messages: Sequence[AcceptedMessage]) -> Tuple[List[Dict[str, object]], Dict[str, object], Dict[str, object]]:
    grouped: Dict[str, List[AcceptedMessage]] = defaultdict(list)
    for message in messages:
        grouped[message.profile].append(message)

    rows: List[Dict[str, object]] = []
    for profile in sorted(grouped.keys()):
        accepted_total = len(grouped[profile])
        accepted_real = sum(1 for message in grouped[profile] if not message.is_canary)
        delivered = failures = deferred = awaiting = unique_opens = total_opens = unique_clicks = total_clicks = 0
        for message in grouped[profile]:
            outcome = message_outcome(message)
            delivered += int(outcome["has_delivered"])
            failures += int(outcome["has_failure"])
            deferred += int(outcome["has_deferred"])
            awaiting += int(outcome["awaiting"])
            unique_opens += int(outcome["open_unique"])
            total_opens += int(outcome["open_total"])
            unique_clicks += int(outcome["click_unique"])
            total_clicks += int(outcome["click_total"])
        failure_rate = (failures / accepted_real) if accepted_real else 0.0
        delivered_rate = (delivered / accepted_real) if accepted_real else 0.0
        open_rate = (unique_opens / delivered) if delivered else 0.0
        click_rate = (unique_clicks / delivered) if delivered else 0.0
        rows.append(
            {
                "profile": profile,
                "accepted_total": accepted_total,
                "accepted_real": accepted_real,
                "canary_count": accepted_total - accepted_real,
                "delivered": delivered,
                "failures": failures,
                "deferred": deferred,
                "awaiting": awaiting,
                "open_unique": unique_opens,
                "open_total": total_opens,
                "click_unique": unique_clicks,
                "click_total": total_clicks,
                "failure_rate": round(failure_rate, 4),
                "delivered_rate": round(delivered_rate, 4),
                "open_rate": round(open_rate, 4),
                "click_rate": round(click_rate, 4),
            }
        )
    eligible = [row for row in rows if row["accepted_real"] > 0]
    best = min(eligible, key=lambda row: (row["failure_rate"], -row["delivered_rate"])) if eligible else {}
    worst = max(eligible, key=lambda row: (row["failure_rate"], row["accepted_real"])) if eligible else {}
    return rows, best, worst


def build_domain_breakdown(messages: Sequence[AcceptedMessage]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[AcceptedMessage]] = defaultdict(list)
    for message in messages:
        if message.is_canary:
            continue
        grouped[message.domain].append(message)

    rows: List[Dict[str, object]] = []
    for domain, domain_messages in grouped.items():
        delivered = failures = deferred = unique_opens = total_opens = unique_clicks = total_clicks = 0
        for message in domain_messages:
            outcome = message_outcome(message)
            delivered += int(outcome["has_delivered"])
            failures += int(outcome["has_failure"])
            deferred += int(outcome["has_deferred"])
            unique_opens += int(outcome["open_unique"])
            total_opens += int(outcome["open_total"])
            unique_clicks += int(outcome["click_unique"])
            total_clicks += int(outcome["click_total"])
        accepted = len(domain_messages)
        rows.append(
            {
                "domain": domain,
                "accepted": accepted,
                "delivered": delivered,
                "failures": failures,
                "deferred": deferred,
                "open_unique": unique_opens,
                "open_total": total_opens,
                "click_unique": unique_clicks,
                "click_total": total_clicks,
                "failure_rate": round((failures / accepted) if accepted else 0.0, 4),
                "delivered_rate": round((delivered / accepted) if accepted else 0.0, 4),
            }
        )
    rows.sort(key=lambda row: (-int(row["failures"]), -int(row["accepted"]), str(row["domain"])))
    return rows


def build_profile_domain_breakdown(messages: Sequence[AcceptedMessage]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str], List[AcceptedMessage]] = defaultdict(list)
    for message in messages:
        if message.is_canary:
            continue
        grouped[(message.profile, message.domain)].append(message)

    rows: List[Dict[str, object]] = []
    for (profile, domain), domain_messages in grouped.items():
        delivered = failures = deferred = unique_opens = total_opens = 0
        for message in domain_messages:
            outcome = message_outcome(message)
            delivered += int(outcome["has_delivered"])
            failures += int(outcome["has_failure"])
            deferred += int(outcome["has_deferred"])
            unique_opens += int(outcome["open_unique"])
            total_opens += int(outcome["open_total"])
        accepted = len(domain_messages)
        rows.append(
            {
                "profile": profile,
                "domain": domain,
                "accepted": accepted,
                "delivered": delivered,
                "failures": failures,
                "deferred": deferred,
                "open_unique": unique_opens,
                "open_total": total_opens,
                "failure_rate": round((failures / accepted) if accepted else 0.0, 4),
                "delivered_rate": round((delivered / accepted) if accepted else 0.0, 4),
            }
        )
    rows.sort(key=lambda row: (-int(row["failures"]), -int(row["accepted"]), str(row["profile"]), str(row["domain"])))
    return rows


def build_bounce_classification_coverage(messages: Sequence[AcceptedMessage]) -> Dict[str, int]:
    bounce_total = 0
    with_classification = 0
    missing_classification = 0
    for message in messages:
        outcome = message_outcome(message)
        event = outcome["failure_event"]
        if not event or canonical_event_status(event.get("status", "")) != "bounce":
            continue
        bounce_total += 1
        if (event.get("bounce_classification") or "").strip():
            with_classification += 1
        else:
            missing_classification += 1
    return {
        "bounces_total": bounce_total,
        "bounces_with_bounce_classification": with_classification,
        "bounces_missing_bounce_classification": missing_classification,
    }


def build_profile_domain_skew(
    profile_rows: Sequence[Dict[str, object]],
    profile_domain_rows: Sequence[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in profile_domain_rows:
        grouped[str(row["profile"])].append(dict(row))

    worst_domain_rows: List[Dict[str, object]] = []
    excluding_top_domain: Dict[str, float] = {}
    for profile_row in profile_rows:
        profile = str(profile_row["profile"])
        domains = grouped.get(profile, [])
        if not domains:
            excluding_top_domain[profile] = round(float(profile_row.get("failure_rate", 0.0) or 0.0), 4)
            continue
        top = max(
            domains,
            key=lambda row: (
                int(row.get("failures", 0) or 0),
                float(row.get("failure_rate", 0.0) or 0.0),
                int(row.get("accepted", 0) or 0),
                str(row.get("domain") or ""),
            ),
        )
        accepted_real = int(profile_row.get("accepted_real", 0) or 0)
        remaining_accepted = max(0, accepted_real - int(top.get("accepted", 0) or 0))
        remaining_failures = max(0, int(profile_row.get("failures", 0) or 0) - int(top.get("failures", 0) or 0))
        excluding_rate = round((remaining_failures / remaining_accepted) if remaining_accepted else 0.0, 4)
        excluding_top_domain[profile] = excluding_rate
        worst_domain_rows.append(
            {
                "profile": profile,
                "domain": str(top.get("domain") or ""),
                "accepted": int(top.get("accepted", 0) or 0),
                "delivered": int(top.get("delivered", 0) or 0),
                "failures": int(top.get("failures", 0) or 0),
                "failure_rate": round(float(top.get("failure_rate", 0.0) or 0.0), 4),
                "share_of_profile_accepted": round((int(top.get("accepted", 0) or 0) / accepted_real) if accepted_real else 0.0, 4),
            }
        )
    worst_domain_rows.sort(key=lambda row: (-int(row["failures"]), -float(row["failure_rate"]), row["profile"]))
    return worst_domain_rows, excluding_top_domain


def build_failure_sections(
    messages: Sequence[AcceptedMessage],
) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]], List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    overall = Counter()
    by_domain: Dict[str, Counter] = defaultdict(Counter)
    reason_counter = Counter()
    unknown_counter: Dict[str, Dict[str, object]] = {}
    failure_rows: List[Dict[str, object]] = []
    for message in messages:
        outcome = message_outcome(message)
        event = outcome["failure_event"]
        if not event:
            continue
        category = str(outcome["failure_category"] or "unknown")
        overall[category] += 1
        by_domain[message.domain][category] += 1
        reason = (event.get("response") or "").strip()
        if reason:
            reason_counter[reason[:REASON_SNIPPET_LIMIT]] += 1
        if category == "unknown":
            key = reason[:REASON_SNIPPET_LIMIT] or f"{(event.get('status') or '').strip()} / {(event.get('code') or '').strip()}"
            bucket = unknown_counter.setdefault(
                key,
                {
                    "reason": key,
                    "count": 0,
                    "profiles": Counter(),
                    "domains": Counter(),
                    "samples": [],
                    "bounce_classification": (event.get("bounce_classification") or "").strip(),
                },
            )
            bucket["count"] += 1
            bucket["profiles"][message.profile] += 1
            bucket["domains"][message.domain] += 1
            if len(bucket["samples"]) < 3:
                bucket["samples"].append(
                    {
                        "profile": message.profile,
                        "email": message.email,
                        "domain": message.domain,
                        "status": canonical_event_status(event.get("status", "")),
                        "code": (event.get("code") or "").strip(),
                    }
                )
        failure_rows.append(
            {
                "profile": message.profile,
                "email": message.email,
                "domain": message.domain,
                "accepted_at_local": message.accepted_at_local,
                "status": canonical_event_status(event.get("status", "")),
                "code": (event.get("code") or "").strip(),
                "category": category,
                "reason": reason[:REASON_SNIPPET_LIMIT],
                "bounce_classification": (event.get("bounce_classification") or "").strip(),
                "message_id": message.message_id,
            }
        )
    latest_failures = sorted(failure_rows, key=lambda row: row["accepted_at_local"], reverse=True)[:20]
    top_reasons = [{"reason": reason, "count": count} for reason, count in reason_counter.most_common(10)]
    by_domain_plain = {domain: dict(counter) for domain, counter in sorted(by_domain.items())}
    unknown_samples = []
    for bucket in sorted(unknown_counter.values(), key=lambda row: (-int(row["count"]), str(row["reason"]))):
        unknown_samples.append(
            {
                "reason": bucket["reason"],
                "count": bucket["count"],
                "bounce_classification": bucket["bounce_classification"],
                "profiles": dict(bucket["profiles"]),
                "domains": dict(bucket["domains"]),
                "samples": bucket["samples"],
            }
        )
    return dict(overall), by_domain_plain, top_reasons, latest_failures, unknown_samples


def should_suppress(outcome_status: str, category: str) -> bool:
    if outcome_status in {"spamreport", "dropped"}:
        return True
    if category in {"mailbox_not_found", "mailbox_disabled", "invalid_recipient"}:
        return True
    return False


def build_suppress_now_rows(
    messages: Sequence[AcceptedMessage],
    suppression_records: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    blocked = {email for email in suppression_records}
    rows: List[Dict[str, str]] = []
    seen: set[str] = set()
    for message in messages:
        if message.is_canary:
            continue
        outcome = message_outcome(message)
        failure_event = outcome["failure_event"]
        if not failure_event:
            continue
        status = str(outcome["final_status"])
        category = str(outcome["failure_category"] or "unknown")
        email = message.email
        if email in blocked or email in seen:
            continue
        if not should_suppress(status, category):
            continue
        seen.add(email)
        rows.append(
            {
                "email": email,
                "profile": message.profile,
                "domain": message.domain,
                "outcome": status,
                "category": category,
                "reason": (failure_event.get("response") or "").strip()[:REASON_SNIPPET_LIMIT],
                "accepted_at_utc": message.accepted_at_utc.isoformat(),
                "accepted_at_local": message.accepted_at_local,
            }
        )
    rows.sort(key=lambda row: (row["domain"], row["email"]))
    return rows


def build_post_run_report(
    root: Path,
    start_utc: datetime,
    end_utc: datetime,
    report_tz: ZoneInfo,
    profile_configs: Optional[Dict[str, Dict[str, object]]] = None,
    suppression_path: Optional[Path] = None,
) -> Dict[str, object]:
    configs = profile_configs or PROFILES
    messages = load_accepted_messages(root, start_utc, end_utc, report_tz, configs)
    events = dedupe_events(load_events_jsonl(root / "sendgrid_events.jsonl"))
    attach_stats = attach_events_to_messages(root, messages, events, configs)
    profile_rows, best_profile, worst_profile = build_profile_summary(messages)
    domain_rows = build_domain_breakdown(messages)
    profile_domain_rows = build_profile_domain_breakdown(messages)
    bounce_classification_coverage = build_bounce_classification_coverage(messages)
    worst_domain_per_profile, profile_failure_rate_excluding_top_domain = build_profile_domain_skew(profile_rows, profile_domain_rows)
    failure_categories, failure_categories_by_domain, top_reasons, latest_failures, unknown_samples = build_failure_sections(messages)
    suppressions = load_suppression_records(suppression_path or (root / "sendgrid_suppressions.csv"))
    suppress_now = build_suppress_now_rows(messages, suppressions)
    totals = {
        "accepted_total": len(messages),
        "real_leads": sum(1 for message in messages if not message.is_canary),
        "canary_count": sum(1 for message in messages if message.is_canary),
        "delivered": sum(int(message_outcome(message)["has_delivered"]) for message in messages),
        "failures": sum(int(message_outcome(message)["has_failure"]) for message in messages),
        "deferred": sum(int(message_outcome(message)["has_deferred"]) for message in messages),
        "awaiting": sum(int(message_outcome(message)["awaiting"]) for message in messages),
        "open_unique": sum(int(message_outcome(message)["open_unique"]) for message in messages),
        "open_total": sum(int(message_outcome(message)["open_total"]) for message in messages),
        "click_unique": sum(int(message_outcome(message)["click_unique"]) for message in messages),
        "click_total": sum(int(message_outcome(message)["click_total"]) for message in messages),
    }
    return {
        "window": {
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
            "timezone": str(report_tz),
        },
        "totals": totals,
        "attach_stats": attach_stats,
        "best_profile": best_profile,
        "worst_profile": worst_profile,
        "profiles": profile_rows,
        "domain_breakdown": domain_rows,
        "profile_domain_breakdown": profile_domain_rows,
        "bounce_classification_coverage": bounce_classification_coverage,
        "worst_domain_per_profile": worst_domain_per_profile,
        "profile_failure_rate_excluding_top_domain": profile_failure_rate_excluding_top_domain,
        "failure_categories": failure_categories,
        "failure_categories_by_domain": failure_categories_by_domain,
        "top_failure_reasons": top_reasons,
        "latest_failures": latest_failures,
        "unknown_samples": unknown_samples,
        "suppress_now": suppress_now,
    }


def report_text(report: Dict[str, object]) -> str:
    window = report["window"]
    totals = report["totals"]
    lines = [
        "Post-Run Report",
        f"Accepted cohort: {window['start_utc']} -> {window['end_utc']} ({window['timezone']})",
        "",
        "Totals",
        f"- Accepted: {totals['accepted_total']} ({totals['real_leads']} real leads, {totals['canary_count']} canaries)",
        f"- Delivered: {totals['delivered']}",
        f"- Failures: {totals['failures']}",
        f"- Deferred: {totals['deferred']}",
        f"- Awaiting outcome: {totals['awaiting']}",
        f"- Unique opens/clicks: {totals['open_unique']} / {totals['click_unique']}",
        "",
    ]
    best = report.get("best_profile") or {}
    worst = report.get("worst_profile") or {}
    if best:
        lines.append(f"Best profile: {best['profile']} (failure_rate={best['failure_rate']:.2%}, delivered_rate={best['delivered_rate']:.2%})")
    if worst:
        lines.append(f"Worst profile: {worst['profile']} (failure_rate={worst['failure_rate']:.2%}, delivered_rate={worst['delivered_rate']:.2%})")
    lines.extend(["", "Profiles"])
    for row in report["profiles"]:
        lines.append(
            f"- {row['profile']}: accepted={row['accepted_real']} real (+{row['canary_count']} canary), "
            f"delivered={row['delivered']}, failures={row['failures']}, deferred={row['deferred']}, "
            f"awaiting={row['awaiting']}, unique_open={row['open_unique']}, failure_rate={row['failure_rate']:.2%}"
        )
    lines.extend(["", "Top Bad Domains"])
    for row in report["domain_breakdown"][:10]:
        if not row["failures"]:
            continue
        lines.append(
            f"- {row['domain']}: accepted={row['accepted']}, failures={row['failures']}, "
            f"failure_rate={row['failure_rate']:.2%}, delivered={row['delivered']}"
        )
    lines.extend(["", "Profile x Domain Hotspots"])
    for row in report["profile_domain_breakdown"][:12]:
        if not row["failures"]:
            continue
        lines.append(
            f"- {row['profile']} / {row['domain']}: accepted={row['accepted']}, failures={row['failures']}, "
            f"failure_rate={row['failure_rate']:.2%}, delivered={row['delivered']}"
        )
    coverage = report.get("bounce_classification_coverage") or {}
    lines.extend(["", "Bounce Classification Coverage"])
    lines.append(
        "- Bounce rows with classification: "
        f"{coverage.get('bounces_with_bounce_classification', 0)} / {coverage.get('bounces_total', 0)} "
        f"(missing={coverage.get('bounces_missing_bounce_classification', 0)})"
    )
    lines.extend(["", "Profile Domain Skew"])
    worst_domain_per_profile = report.get("worst_domain_per_profile") or []
    excluding_top_domain = report.get("profile_failure_rate_excluding_top_domain") or {}
    for row in worst_domain_per_profile:
        lines.append(
            f"- {row['profile']}: top drag={row['domain']} ({row['failures']} failures / {row['accepted']} accepted, "
            f"failure_rate={row['failure_rate']:.2%}), excluding_top_domain={float(excluding_top_domain.get(row['profile'], 0.0)):.2%}"
        )
    lines.extend(["", "Failure Categories"])
    for category, count in sorted(report["failure_categories"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "Top Failure Reasons"])
    for row in report["top_failure_reasons"]:
        lines.append(f"- {row['count']}x {row['reason']}")
    lines.extend(["", f"Suppress Now: {len(report['suppress_now'])} new email(s)"])
    return "\n".join(lines).rstrip() + "\n"


def unknown_samples_text(report: Dict[str, object]) -> str:
    rows = report.get("unknown_samples") or []
    if not rows:
        return "No unknown failure samples.\n"
    lines = ["Unknown Failure Samples"]
    for row in rows:
        lines.extend(
            [
                "",
                f"Count: {row['count']}",
                f"Reason: {row['reason']}",
                f"Bounce classification: {row.get('bounce_classification') or '-'}",
                f"Profiles: {json.dumps(row['profiles'], sort_keys=True)}",
                f"Domains: {json.dumps(row['domains'], sort_keys=True)}",
                "Samples:",
            ]
        )
        for sample in row.get("samples", []):
            lines.append(
                f"- {sample['profile']} | {sample['email']} | {sample['domain']} | {sample['status']} {sample['code']}".rstrip()
            )
    return "\n".join(lines).rstrip() + "\n"


def write_csv(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["email", "profile", "domain", "outcome", "category", "reason", "accepted_at_utc", "accepted_at_local"])
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def apply_suppressions(suppression_path: Path, rows: Sequence[Dict[str, str]]) -> int:
    records = load_suppression_records(suppression_path)
    added = 0
    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if not email or email in records:
            continue
        records[email] = {
            "email": email,
            "status": row.get("outcome", "bounce"),
            "code": "",
            "reason": row.get("reason", ""),
            "last_seen_utc": row.get("accepted_at_utc", ""),
            "is_permanent": "true",
            "ttl_until_utc": "",
        }
        added += 1
    if added:
        write_suppression_records(suppression_path, records)
    return added


def default_out_dir(root: Path, label: str) -> Path:
    return root / "reports" / label


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build post-run report from SendGrid sender logs and webhook events.")
    parser.add_argument("--date", help="Local report date in YYYY-MM-DD format.")
    parser.add_argument("--since", help="Accepted cohort start timestamp in ISO-8601 UTC.")
    parser.add_argument("--until", help="Accepted cohort end timestamp in ISO-8601 UTC.")
    parser.add_argument("--timezone", default=REPORT_TZ_NAME, help="Report timezone for --date and display output.")
    parser.add_argument("--out-dir", default="", help="Output directory. Defaults to reports/<label>.")
    parser.add_argument("--apply-suppressions", action="store_true", help="Append new suppressions into sendgrid_suppressions.csv.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    report_tz = resolve_report_timezone(args.timezone)
    start_utc, end_utc, label = parse_window_args(args, report_tz)
    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir(ROOT, label)
    suppression_path = ROOT / "sendgrid_suppressions.csv"
    report = build_post_run_report(ROOT, start_utc, end_utc, report_tz, suppression_path=suppression_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    text_path = out_dir / "post_run_report.txt"
    json_path = out_dir / "post_run_report.json"
    suppress_path = out_dir / "suppress_now.csv"
    unknown_path = out_dir / "unknown_samples.txt"

    text_path.write_text(report_text(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    write_csv(suppress_path, report["suppress_now"])
    unknown_path.write_text(unknown_samples_text(report), encoding="utf-8")

    applied = 0
    if args.apply_suppressions:
        applied = apply_suppressions(suppression_path, report["suppress_now"])

    print(report_text(report), end="")
    print(f"Wrote: {text_path}")
    print(f"Wrote: {json_path}")
    print(f"Wrote: {suppress_path}")
    print(f"Wrote: {unknown_path}")
    if args.apply_suppressions:
        print(f"Applied suppressions: {applied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
