#!/usr/bin/env python3
"""Helpers for deciding whether a job posting is recent and still active."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

MAX_AGE_DAYS = 180

INACTIVE_KEYWORDS = [
    "no longer accepting",
    "no longer accepting applications",
    "position filled",
    "position has been filled",
    "closed",
    "expired",
    "archived",
    "no longer available",
    "not currently hiring",
    "application deadline passed",
    "requisition closed",
    "job is no longer available",
    "posting has expired",
]

NOT_FOUND_KEYWORDS = [
    "page not found",
    "could not be found",
    "job not found",
    "sorry, the page you requested could not be found",
    "this page isn’t available",
    "this page isn't available",
    "the page you requested could not be found",
]


def normalize_text(*parts: Optional[str]) -> str:
    return " ".join((p or "").strip() for p in parts if p).strip()


def _coerce_iso_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).strftime("%Y-%m-%d")
    except Exception:
        return None


def is_recent_iso_date(value: Optional[str], max_age_days: int = MAX_AGE_DAYS) -> bool:
    iso = _coerce_iso_date(value)
    if not iso:
        return False
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        return dt >= datetime.now() - timedelta(days=max_age_days)
    except Exception:
        return False


def _extract_relative_age(text: str) -> Optional[Dict[str, Any]]:
    lower = text.lower()
    now = datetime.now()

    quick_tokens = {
        "just posted": 0,
        "just now": 0,
        "today": 0,
        "yesterday": 1,
    }
    for token, days_old in quick_tokens.items():
        if token in lower:
            posted = (now - timedelta(days=days_old)).strftime("%Y-%m-%d")
            return {"days_old": days_old, "date_posted": posted, "age_text": token}

    patterns = [
        (r"(?:reposted|posted)?\s*(\d+)\+?\s+day[s]?\s+ago", 1, "days"),
        (r"(?:reposted|posted)?\s*(\d+)\+?\s+week[s]?\s+ago", 7, "weeks"),
        (r"(?:reposted|posted)?\s*(\d+)\+?\s+month[s]?\s+ago", 30, "months"),
        (r"(?:reposted|posted)?\s*(\d+)\+?\s+year[s]?\s+ago", 365, "years"),
    ]

    for pattern, multiplier, unit in patterns:
        match = re.search(pattern, lower)
        if not match:
            continue
        num = int(match.group(1))
        days_old = num * multiplier
        posted = (now - timedelta(days=days_old)).strftime("%Y-%m-%d")
        age_text = f"{num} {unit[:-1] if num == 1 else unit} ago"
        return {"days_old": days_old, "date_posted": posted, "age_text": age_text}

    return None


def assess_job_freshness(
    title: Optional[str] = None,
    description: Optional[str] = None,
    notes: Optional[str] = None,
    url: Optional[str] = None,
    source: Optional[str] = None,
    explicit_date_posted: Optional[str] = None,
    max_age_days: int = MAX_AGE_DAYS,
) -> Dict[str, Any]:
    text = normalize_text(title, description, notes)
    lower = text.lower()
    url_lower = (url or "").lower()
    source_lower = (source or "").lower()
    is_linkedin_wrapper = "linkedin.com/jobs" in url_lower or source_lower == "linkedin"

    for keyword in NOT_FOUND_KEYWORDS:
        if keyword in lower:
            return {
                "keep": False,
                "active": False,
                "verified": True,
                "date_posted": _coerce_iso_date(explicit_date_posted),
                "days_old": None,
                "reason": f"Listing content indicates a dead page: {keyword}",
            }

    for keyword in INACTIVE_KEYWORDS:
        if keyword in lower:
            return {
                "keep": False,
                "active": False,
                "verified": True,
                "date_posted": _coerce_iso_date(explicit_date_posted),
                "days_old": None,
                "reason": f"Listing content indicates the job is inactive: {keyword}",
            }

    explicit_iso = _coerce_iso_date(explicit_date_posted)
    if explicit_iso:
        posted_dt = datetime.strptime(explicit_iso, "%Y-%m-%d")
        days_old = (datetime.now() - posted_dt).days
        if days_old > max_age_days:
            return {
                "keep": False,
                "active": False,
                "verified": True,
                "date_posted": explicit_iso,
                "days_old": days_old,
                "reason": f"Explicit posted date is too old: {explicit_iso}",
            }
        return {
            "keep": True,
            "active": True,
            "verified": True,
            "date_posted": explicit_iso,
            "days_old": days_old,
            "reason": f"Explicit posted date verified: {explicit_iso}",
        }

    age_info = _extract_relative_age(lower)
    if age_info:
        if age_info["days_old"] > max_age_days:
            return {
                "keep": False,
                "active": False,
                "verified": True,
                "date_posted": age_info["date_posted"],
                "days_old": age_info["days_old"],
                "reason": f"Listing says {age_info['age_text']}",
            }
        return {
            "keep": True,
            "active": True,
            "verified": True,
            "date_posted": age_info["date_posted"],
            "days_old": age_info["days_old"],
            "reason": f"Freshness verified from listing text: {age_info['age_text']}",
        }

    if is_linkedin_wrapper:
        return {
            "keep": False,
            "active": False,
            "verified": False,
            "date_posted": None,
            "days_old": None,
            "reason": "LinkedIn wrapper without verifiable posting age or active-status signal",
        }

    return {
        "keep": True,
        "active": True,
        "verified": False,
        "date_posted": None,
        "days_old": None,
        "reason": "No explicit freshness signal found",
    }


def best_reference_date(job: Dict[str, Any]) -> Optional[str]:
    url = (job.get("url") or "").lower()
    source = (job.get("source") or "").lower()
    if job.get("date_posted"):
        return _coerce_iso_date(job.get("date_posted"))
    if "linkedin.com/jobs" in url or source == "linkedin":
        return None
    return _coerce_iso_date(job.get("date_found"))
