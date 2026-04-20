#!/usr/bin/env python3
"""
Daily Job Search - Automated Pipeline
Searches multiple sources, filters results, updates tracker, pushes to GitHub
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from job_freshness import assess_job_freshness, best_reference_date

DATA_DIR = Path(__file__).parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
ARCHIVE_FILE = DATA_DIR / "archived_jobs.json"
REPORTS_DIR = Path(__file__).parent / "reports"

# Search queries optimized for Varun's profile
SEARCH_QUERIES = [
    # Core analytical chemistry roles
    '"Analytical Development" scientist "PhD" biotech',
    '"CMC Analytical" scientist pharmaceutical',
    '"Quality Control" scientist chemistry "PhD"',
    '"Formulation" scientist analytical chemistry',
    '"Materials Characterization" scientist PhD',
    # Specific companies
    'site:linkedin.com/jobs "Genentech" "Scientist" analytical',
    'site:linkedin.com/jobs "Amgen" "Scientist" chemistry',
    'site:linkedin.com/jobs "Gilead" "Scientist" analytical',
    'site:linkedin.com/jobs "BMS" "Scientist" analytical',
    # Job boards
    'site:jobs.lever.co "Scientist" analytical chemistry',
    'site:boards.greenhouse.io "Scientist" analytical development',
]

def load_jobs():
    if JOBS_FILE.exists():
        with open(JOBS_FILE) as f:
            return json.load(f)
    return []

def save_jobs(jobs):
    with open(JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=2)

def archive_old_jobs(jobs, days=180):
    """Move jobs older than cutoff to archive."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    recent, old = [], []
    for job in jobs:
        ref_date = best_reference_date(job)
        if ref_date and ref_date < cutoff:
            old.append(job)
        else:
            recent.append(job)
    
    if old:
        archived = []
        if ARCHIVE_FILE.exists():
            with open(ARCHIVE_FILE) as f:
                archived = json.load(f)
        existing_urls = {j.get('url') for j in archived}
        for job in old:
            if job.get('url') not in existing_urls:
                archived.append(job)
        with open(ARCHIVE_FILE, 'w') as f:
            json.dump(archived, f, indent=2)
        print(f"Archived {len(old)} old jobs")
    
    return recent

def is_duplicate(jobs, url):
    """Check if job URL already exists"""
    return any(j.get('url') == url for j in jobs)

def parse_job_from_result(result, query):
    """Parse web search result into job dict."""
    url = result.get('url', '')
    title = result.get('title', '').replace('\n', ' ').strip()
    desc = result.get('description', '')

    # Skip non-job URLs
    if not any(x in url.lower() for x in ['jobs', 'careers', 'linkedin.com/jobs', 'lever.co', 'greenhouse.io']):
        return None

    freshness = assess_job_freshness(title=title, description=desc, url=url, source='automated_search')
    if not freshness['keep']:
        return None
    
    # Extract company from URL or title
    company = "Unknown"
    if 'linkedin.com' in url:
        parts = url.split('/')
        if len(parts) > 5:
            company = parts[4].replace('-', ' ').title()
    elif 'lever.co' in url:
        parts = url.split('/')
        if len(parts) > 3:
            company = parts[2].replace('.lever.co', '').title()
    
    # Clean up title
    title = title.replace('| LinkedIn', '').replace('hiring', '').strip()
    
    # Extract location
    location = "Unknown"
    for loc in ['San Francisco', 'Boston', 'San Diego', 'Cambridge', 'South San Francisco', 'Menlo Park']:
        if loc.lower() in desc.lower():
            location = loc
            break
    
    return {
        "source": "automated_search",
        "title": title[:120],
        "company": company[:50],
        "location": location,
        "url": url,
        "description": desc[:300],
        "date_found": datetime.now().strftime('%Y-%m-%d'),
        "date_posted": freshness.get('date_posted'),
        "freshness_verified": freshness.get('verified', False),
        "freshness_reason": freshness.get('reason'),
        "job_id": None,
        "status": "discovered",
        "score": None,
        "archetype": "Analytical / Quality Scientist",
        "applied_date": None,
        "follow_up_date": None,
        "notes": f"Found via automated search: {query[:40]}... Freshness: {freshness.get('reason')}",
        "evaluation": None,
        "report_path": None,
        "pdf_path": None,
        "tailored_resume": None
    }

def git_commit_push():
    """Commit and push changes to GitHub"""
    try:
        subprocess.run(['git', 'add', '-A'], cwd=Path(__file__).parent, check=True)
        commit_msg = f"Daily job search update - {datetime.now().strftime('%Y-%m-%d')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], cwd=Path(__file__).parent, check=True)
        subprocess.run(['git', 'push'], cwd=Path(__file__).parent, check=True)
        print("✅ Pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git operation failed: {e}")
        return False

def generate_report(new_jobs, total_jobs):
    """Generate daily report"""
    REPORTS_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    report = f"""# Daily Job Search Report - {date_str}

## Summary
- **New jobs found:** {len(new_jobs)}
- **Total active jobs:** {total_jobs}
- **Search completed:** {datetime.now().strftime('%H:%M')}

## New Jobs
"""
    for job in new_jobs:
        report += f"- {job['title']} @ {job['company']} ({job['location']})\n"
    
    report_path = REPORTS_DIR / f"daily_report_{date_str}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    return report_path

if __name__ == "__main__":
    print("=" * 60)
    print(f"Daily Job Search - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Load current jobs
    jobs = load_jobs()
    print(f"Loaded {len(jobs)} current jobs")
    
    # Archive old jobs
    jobs = archive_old_jobs(jobs)
    print(f"After archiving: {len(jobs)} recent jobs")
    
    # Note: Actual web search requires OpenClaw agent with web_search tool
    # This script is designed to be called by OpenClaw which has that capability
    
    print("\nNote: To run full search, use:")
    print("  openclaw cron: run this script with web_search enabled")
    
    # Save current state
    save_jobs(jobs)
    
    print("\n✅ Daily maintenance complete")
    print(f"   Active jobs: {len(jobs)}")
