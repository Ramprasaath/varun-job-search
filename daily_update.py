#!/usr/bin/env python3
"""
Daily Job Update Script
Runs job search, filters for recent/active jobs, updates tracker
Designed to be run via cron
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
ARCHIVE_FILE = DATA_DIR / "archived_jobs.json"

def load_jobs():
    if JOBS_FILE.exists():
        with open(JOBS_FILE) as f:
            return json.load(f)
    return []

def save_jobs(jobs):
    with open(JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=2)

def archive_old_jobs(jobs, days=180):
    """Move jobs older than 6 months to archive"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    recent = [j for j in jobs if j.get('date_found', '') >= cutoff]
    old = [j for j in jobs if j.get('date_found', '') < cutoff]
    
    if old:
        archived = []
        if ARCHIVE_FILE.exists():
            with open(ARCHIVE_FILE) as f:
                archived = json.load(f)
        
        # Add old jobs to archive (avoid duplicates)
        existing_urls = {j.get('url') for j in archived}
        for job in old:
            if job.get('url') not in existing_urls:
                archived.append(job)
        
        with open(ARCHIVE_FILE, 'w') as f:
            json.dump(archived, f, indent=2)
        
        print(f"Archived {len(old)} old jobs to {ARCHIVE_FILE}")
    
    return recent

def run_job_search():
    """Run the daily pipeline search"""
    print(f"Running job search at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # This would call your web search functions
    # For now, it's a placeholder that you can expand
    # You'd integrate with your OpenClaw agent or search API here
    
    print("Note: Actual search requires OpenClaw agent with web_search tool")
    print("This script prepares the framework for automated updates")
    
    return []

if __name__ == "__main__":
    print("=" * 60)
    print("Daily Job Update - " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 60)
    
    # Load current jobs
    jobs = load_jobs()
    print(f"Loaded {len(jobs)} current jobs")
    
    # Archive old jobs
    jobs = archive_old_jobs(jobs)
    print(f"After archiving: {len(jobs)} recent jobs")
    
    # Save updated jobs
    save_jobs(jobs)
    
    print("✅ Daily update complete")
    print(f"Next: Run 'git add . && git commit -m \"Daily job update\" && git push'")
    print("Or integrate with OpenClaw agent for automatic search")
