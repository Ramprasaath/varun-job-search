#!/usr/bin/env python3
"""
Import LinkedIn scraped jobs into the main tracker
"""

import json
import sys
from datetime import datetime

def is_job_recent(job: dict, max_days: int = 180) -> bool:
    """Check if job is within last 6 months (180 days)"""
    from datetime import datetime, timedelta
    
    date_str = job.get('date_found') or job.get('date_posted')
    if not date_str:
        return True  # If no date, assume recent
    
    try:
        job_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
        cutoff = datetime.now() - timedelta(days=max_days)
        return job_date >= cutoff
    except:
        return True

def is_job_active(job: dict) -> bool:
    """Check if job is still accepting applications"""
    title = job.get('title', '').lower()
    notes = job.get('notes', '').lower()
    
    inactive_keywords = [
        'no longer accepting', 'position filled', 'closed', 'expired',
        'archived', 'no longer available', 'position has been filled',
        'not currently hiring', 'application deadline passed', 'requisition closed'
    ]
    
    text = title + ' ' + notes
    return not any(keyword in text for keyword in inactive_keywords)

def import_linkedin_jobs(linkedin_file: str, tracker_file: str, max_age_days: int = 180):
    """
    Merge LinkedIn jobs into the main tracker
    
    Args:
        linkedin_file: Path to linkedin_jobs_YYYYMMDD.json
        tracker_file: Path to streamlit-app/data/jobs.json
        max_age_days: Only import jobs posted within this many days (default 180 = 6 months)
    """
    from datetime import datetime
    
    # Load LinkedIn jobs
    with open(linkedin_file, 'r') as f:
        linkedin_jobs = json.load(f)
    
    # Load existing tracker
    with open(tracker_file, 'r') as f:
        tracker = json.load(f)
    
    # Get next ID
    next_id = max([j.get('id', 0) for j in tracker], default=0) + 1
    
    # Track what's new
    added = []
    skipped = []
    too_old = []
    inactive = []
    
    for job in linkedin_jobs:
        # Check if job is recent (within 6 months)
        if not is_job_recent(job, max_age_days):
            too_old.append(job)
            continue
        
        # Check if job is still active
        if not is_job_active(job):
            inactive.append(job)
            continue
        
        # Check for duplicates by URL
        existing = [j for j in tracker if j.get('url') == job.get('url')]
        
        if existing:
            skipped.append(job)
            continue
    
    for job in linkedin_jobs:
        # Check for duplicates by URL
        existing = [j for j in tracker if j.get('url') == job.get('url')]
        
        if existing:
            skipped.append(job)
            continue
        
        # Prepare job for tracker
        job['id'] = next_id
        next_id += 1
        
        # Set defaults for tracker format
        job['archetype'] = "Analytical / Quality Scientist"  # Default archetype
        job['applied_date'] = None
        job['follow_up_date'] = None
        job['notes'] = f"Found via LinkedIn search on {job.get('date_found', datetime.now().strftime('%Y-%m-%d'))}"
        job['tailored_resume'] = None
        
        tracker.append(job)
        added.append(job)
    
    # Save updated tracker
    with open(tracker_file, 'w') as f:
        json.dump(tracker, f, indent=2)
    
    print(f"✅ Import complete!")
    print(f"   Added: {len(added)} new jobs")
    print(f"   Skipped (duplicates): {len(skipped)}")
    print(f"   Skipped (too old >{max_age_days} days): {len(too_old)}")
    print(f"   Skipped (inactive/not accepting): {len(inactive)}")
    print(f"   Total tracker jobs: {len(tracker)}")
    
    return added

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_linkedin_jobs.py <linkedin_jobs_file.json>")
        print("Example: python import_linkedin_jobs.py linkedin_jobs_2026-04-14.json")
        sys.exit(1)
    
    linkedin_file = sys.argv[1]
    tracker_file = "/Users/ram/varun-career-ops/streamlit-app/data/jobs.json"
    
    import_linkedin_jobs(linkedin_file, tracker_file)
