#!/usr/bin/env python3
"""Import LinkedIn scraped jobs into the main tracker conservatively."""

import json
import sys
from datetime import datetime
from pathlib import Path

from job_freshness import assess_job_freshness, best_reference_date, is_recent_iso_date


def import_linkedin_jobs(linkedin_file: str, tracker_file: str, max_age_days: int = 180):
    """
    Merge LinkedIn jobs into the main tracker.

    Rules:
    - prefer `date_posted` over `date_found`
    - never treat LinkedIn discovery date as posting age
    - skip LinkedIn wrappers that do not have verifiable freshness
    - skip inactive / closed jobs
    - skip duplicates by URL
    """
    with open(linkedin_file, 'r') as f:
        linkedin_jobs = json.load(f)

    with open(tracker_file, 'r') as f:
        tracker = json.load(f)

    next_id = max([j.get('id', 0) for j in tracker], default=0) + 1
    existing_urls = {j.get('url') for j in tracker}

    added = []
    skipped = []
    too_old = []
    inactive = []
    unverified = []

    for job in linkedin_jobs:
        url = job.get('url', '')
        source = job.get('source', 'linkedin')
        freshness = assess_job_freshness(
            title=job.get('title'),
            description=job.get('description'),
            notes=job.get('notes'),
            url=url,
            source=source,
            explicit_date_posted=job.get('date_posted'),
            max_age_days=max_age_days,
        )

        if url in existing_urls:
            skipped.append(job)
            continue

        if not freshness.get('verified') and ('linkedin.com/jobs' in url.lower() or source == 'linkedin'):
            unverified.append(job)
            continue

        if not freshness.get('active'):
            ref_date = freshness.get('date_posted') or best_reference_date(job)
            if ref_date and not is_recent_iso_date(ref_date, max_age_days=max_age_days):
                too_old.append(job)
            else:
                inactive.append(job)
            continue

        job['id'] = next_id
        next_id += 1
        job['source'] = source
        job['date_posted'] = freshness.get('date_posted') or job.get('date_posted')
        job['freshness_verified'] = freshness.get('verified', False)
        job['freshness_reason'] = freshness.get('reason')
        job['archetype'] = job.get('archetype') or 'Analytical / Quality Scientist'
        job['applied_date'] = job.get('applied_date')
        job['follow_up_date'] = job.get('follow_up_date')
        base_note = f"Found via LinkedIn search on {job.get('date_found', datetime.now().strftime('%Y-%m-%d'))}"
        extra_note = freshness.get('reason')
        job['notes'] = f"{base_note}. Freshness: {extra_note}" if extra_note else base_note
        job['tailored_resume'] = job.get('tailored_resume')

        tracker.append(job)
        existing_urls.add(url)
        added.append(job)

    with open(tracker_file, 'w') as f:
        json.dump(tracker, f, indent=2)

    print("✅ Import complete!")
    print(f"   Added: {len(added)} new jobs")
    print(f"   Skipped (duplicates): {len(skipped)}")
    print(f"   Skipped (too old >{max_age_days} days): {len(too_old)}")
    print(f"   Skipped (inactive/not accepting): {len(inactive)}")
    print(f"   Skipped (unverified LinkedIn freshness): {len(unverified)}")
    print(f"   Total tracker jobs: {len(tracker)}")

    return added


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_linkedin_jobs.py <linkedin_jobs_file.json>")
        print("Example: python import_linkedin_jobs.py linkedin_jobs_2026-04-14.json")
        sys.exit(1)

    linkedin_file = sys.argv[1]
    tracker_file = str(Path(__file__).parent / 'data' / 'jobs.json')

    import_linkedin_jobs(linkedin_file, tracker_file)
