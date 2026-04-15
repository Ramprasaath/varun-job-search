#!/usr/bin/env python3
"""
Import LinkedIn scraped jobs into the main tracker
"""

import json
import sys
from datetime import datetime

def import_linkedin_jobs(linkedin_file: str, tracker_file: str):
    """
    Merge LinkedIn jobs into the main tracker
    
    Args:
        linkedin_file: Path to linkedin_jobs_YYYYMMDD.json
        tracker_file: Path to streamlit-app/data/jobs.json
    """
    
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
