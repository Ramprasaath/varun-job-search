#!/usr/bin/env python3
"""
Daily Job Pipeline for Varun
Runs comprehensive multi-site search, imports to tracker, scores, generates resumes
"""

import json
import time
from datetime import datetime
from pathlib import Path

from job_freshness import assess_job_freshness

# All search queries for daily sweep
DAILY_SEARCHES = [
    # LinkedIn - Core searches
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Senior Scientist" "Analytical Chemistry"', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Scientist" "CMC Analytical" OR "Analytical Development"', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Scientist" "Formulation" pharmaceutical', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Scientist" "Quality Control" biotech', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Materials" characterization scientist', "count": 10},
    
    # Indeed
    {"platform": "indeed", "query": 'site:indeed.com "Scientist" "Analytical Chemistry" biotech', "count": 10},
    {"platform": "indeed", "query": 'site:indeed.com "Analytical Development" scientist', "count": 10},
    {"platform": "indeed", "query": 'site:indeed.com "CMC" "Analytical" scientist', "count": 10},
    {"platform": "indeed", "query": 'site:indeed.com "Formulation" scientist pharmaceutical', "count": 10},
    
    # Wellfound (Startups)
    {"platform": "wellfound", "query": 'site:wellfound.com/jobs "scientist" chemistry biotech', "count": 10},
    {"platform": "wellfound", "query": 'site:wellfound.com/jobs "analytical" scientist', "count": 10},
    
    # BioSpace
    {"platform": "biospace", "query": 'site:biospace.com jobs "Analytical Development" scientist', "count": 10},
    {"platform": "biospace", "query": 'site:biospace.com jobs "CMC" scientist', "count": 10},
    {"platform": "biospace", "query": 'site:biospace.com jobs "Formulation" scientist', "count": 10},
    
    # Company-specific searches (major biotechs without Lever)
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Genentech" "Scientist" analytical', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Amgen" "Scientist" analytical chemistry', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Gilead" "Scientist" analytical', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Pfizer" "Scientist" analytical chemistry', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "BMS" "Scientist" analytical', "count": 10},
    
    # Additional biotech hubs
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Scientist" analytical "San Diego" biotech', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Scientist" analytical "Boston" biotech', "count": 10},
    {"platform": "linkedin", "query": 'site:linkedin.com/jobs "Scientist" analytical "Cambridge" MA', "count": 10},
]

def get_next_id(tracker_path: str) -> int:
    """Get next job ID from tracker"""
    try:
        with open(tracker_path, 'r') as f:
            jobs = json.load(f)
            return max([j.get('id', 0) for j in jobs], default=0) + 1
    except:
        return 1

def assess_result_freshness(title: str, description: str, url: str, platform: str) -> dict:
    """Conservative freshness gate for search results."""
    return assess_job_freshness(
        title=title,
        description=description,
        url=url,
        source=platform,
        max_age_days=180,
    )

def parse_search_result(result: dict, platform: str, query: str) -> dict:
    """Parse a web search result into job format"""
    import re
    
    url = result.get('url', '')
    title = result.get('title', '').replace('\n', '').strip()
    description = result.get('description', '')
    
    freshness = assess_result_freshness(title, description, url, platform)
    if not freshness["keep"]:
        return None
    
    # Extract company
    company = "Unknown"
    if 'linkedin.com' in url:
        # Extract from URL: at-company-name-
        match = re.search(r'at-([a-z0-9-]+)-\d+$', url.lower())
        if match:
            company = match.group(1).replace('-', ' ').title()
    elif 'indeed.com' in url:
        company_match = re.search(r'View all ([^\']+) jobs', description)
        if company_match:
            company = company_match.group(1)
    
    # Clean title
    title = title.split('|')[0].strip()
    title = title.replace('hiring ', '').replace('Jobs, Employment', '')
    
    # Extract location
    location = "Unknown"
    loc_patterns = [
        r'in ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*(?:CA|MA|NY|NJ|WA|TX|NC|CT))',
        r'(San Francisco|Boston|San Diego|Cambridge|South San Francisco)',
    ]
    for pattern in loc_patterns:
        match = re.search(pattern, description)
        if match:
            location = match.group(1)
            break
    
    return {
        "source": platform,
        "title": title[:100],
        "company": company[:50],
        "location": location,
        "url": url,
        "description": description[:300],
        "date_found": datetime.now().strftime("%Y-%m-%d"),
        "date_posted": freshness.get("date_posted"),
        "freshness_verified": freshness.get("verified", False),
        "freshness_reason": freshness.get("reason"),
        "job_id": None,
        "status": "discovered",
        "score": None,
        "archetype": "Analytical / Quality Scientist",
        "applied_date": None,
        "follow_up_date": None,
        "notes": f"Found via {platform} search: {query[:50]}... Freshness: {freshness.get('reason')}",
        "evaluation": None,
        "report_path": None,
        "pdf_path": None,
        "tailored_resume": None
    }

def generate_daily_report(jobs_found: list, tracker_path: str) -> str:
    """Generate a daily summary report"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Get current tracker stats
    with open(tracker_path, 'r') as f:
        tracker = json.load(f)
    
    total_jobs = len(tracker)
    evaluated = len([j for j in tracker if j.get('status') == 'evaluated'])
    high_score = len([j for j in tracker if j.get('score') and j.get('score') >= 4.0])
    
    report = f"""# Daily Pipeline Report - {date_str}

## Summary
- **New jobs found today:** {len(jobs_found)}
- **Total jobs in tracker:** {total_jobs}
- **Jobs evaluated:** {evaluated}
- **High-quality matches (4.0+):** {high_score}

## New Jobs Added
"""
    
    for job in jobs_found[:20]:  # Limit to first 20
        report += f"- {job['title']} @ {job['company']} ({job['location']})\n"
    
    if len(jobs_found) > 20:
        report += f"- ... and {len(jobs_found) - 20} more\n"
    
    report += f"""
## Next Steps
1. Review new jobs in tracker
2. Score promising matches (target 4.0+)
3. Generate tailored resumes for high scores
4. Find LinkedIn contacts for outreach

## Tracker Location
`/Users/ram/Projects/varun-job-search/data/jobs.json`

Run Streamlit app to review:
```bash
cd /Users/ram/Projects/varun-job-search && streamlit run app.py
```
"""
    
    report_path = f"/Users/ram/Projects/varun-job-search/reports/daily_report_{date_str}.md"
    Path(report_path).parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    return report_path

if __name__ == "__main__":
    print("Daily Pipeline Configuration")
    print(f"Total searches: {len(DAILY_SEARCHES)}")
    print(f"Estimated time: {len(DAILY_SEARCHES) * 3 // 60} minutes (with rate limiting)")
    print("\nThis script provides the search configuration.")
    print("To run the full pipeline with web_search integration, use the OpenClaw agent.")
