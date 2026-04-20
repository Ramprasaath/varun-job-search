#!/usr/bin/env python3
"""
Multi-Site Job Search for Varun's Pipeline
Searches LinkedIn, Indeed, BioSpace, and other job sites via Brave/Google
"""

import json
import time
import random
from datetime import datetime
from typing import List, Dict
import subprocess
import re

from job_freshness import assess_job_freshness

# Search queries for different platforms
SEARCH_CONFIG = {
    "linkedin": {
        "queries": [
            'site:linkedin.com/jobs ("Materials Scientist" OR "Materials Engineer" OR "Characterization Engineer") thin film OR coatings OR polymer',
            'site:linkedin.com/jobs ("Failure Analysis Engineer" OR "Reliability Engineer" OR "Reliability Scientist") materials OR semiconductor OR chemistry',
            'site:linkedin.com/jobs ("Process Development Scientist" OR "Process Chemist" OR "Formulation Scientist") polymer OR coatings OR scale-up',
            'site:linkedin.com/jobs ("Applications Scientist" OR "Field Application Scientist") spectroscopy OR chromatography OR materials',
            'site:linkedin.com/jobs ("Analytical Development" OR "CMC Analytical" OR "Analytical Scientist") "small molecule"',
            'site:linkedin.com/jobs ("Process Engineer" OR metrology OR deposition OR "Characterization Engineer") semiconductor OR thin film',
        ],
        "results_per_query": 5
    },
    "indeed": {
        "queries": [
            'site:indeed.com ("Materials Scientist" OR "Analytical Scientist") polymer OR coatings OR characterization',
            'site:indeed.com ("Failure Analysis" OR "Reliability Engineer") materials OR chemistry OR semiconductor',
            'site:indeed.com ("Process Chemist" OR "Development Chemist" OR "Formulation Scientist") polymer OR coating OR chemistry',
            'site:indeed.com ("Applications Scientist" OR spectroscopy OR chromatography) materials OR chemistry',
        ],
        "results_per_query": 5
    },
    "wellfound": {
        "queries": [
            'site:wellfound.com/jobs ("materials scientist" OR chemist OR analytical) startup biotech OR battery OR semiconductor',
            'site:wellfound.com/jobs (polymer OR coatings OR characterization OR "applications scientist")',
            'site:angel.co/jobs ("scientist" OR "materials" OR chemist) startup',
        ],
        "results_per_query": 4
    },
    "biospace": {
        "queries": [
            'site:biospace.com jobs ("Analytical Development" OR "CMC Analytical") "small molecule"',
            'site:biospace.com jobs ("Formulation Scientist" OR "Process Development") chemistry OR materials',
            'site:biospace.com jobs ("Applications Scientist" OR "Analytical Scientist")',
        ],
        "results_per_query": 5
    }
}


def run_brave_search(query: str, count: int = 5) -> List[Dict]:
    """
    Run Brave search via openclaw web_search
    Note: This is a placeholder - in actual use, this would call web_search tool
    """
    # In real implementation, this would use the web_search tool
    # For now, we document the expected structure
    return []


def parse_job_from_result(result: Dict, source: str) -> Dict:
    """Parse a search result into tracker-compatible job format."""
    url = result.get('url', '')
    title = result.get('title', '').strip()
    description = result.get('description', '')

    freshness = assess_job_freshness(title=title, description=description, url=url, source=source)
    if not freshness['keep']:
        return None

    # Extract company from title or URL
    company = "Unknown"
    
    # LinkedIn pattern
    if 'linkedin.com' in url:
        match = re.search(r'at-([a-z-]+)-\d+', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
        # Also check title
        if ' at ' in title:
            company = title.split(' at ')[-1].split('|')[0].strip()
    
    # Indeed pattern
    elif 'indeed.com' in url:
        company_match = re.search(r'View all ([^\']+) jobs', description)
        if company_match:
            company = company_match.group(1)
    
    # BioSpace pattern
    elif 'biospace.com' in url:
        company_match = re.search(r'at ([^\|]+)\|', title)
        if company_match:
            company = company_match.group(1).strip()
    
    # Extract location
    location = "Unknown"
    location_patterns = [
        r'in ([A-Za-z\s,]+(?:CA|MA|NY|NJ|WA|TX|NC))',
        r'location[:\s]+([A-Za-z\s,]+)',
    ]
    for pattern in location_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            break
    
    return {
        "source": source,
        "title": title.split('|')[0].strip() if '|' in title else title,
        "company": company,
        "location": location,
        "url": url,
        "description": description[:500],
        "date_found": datetime.now().strftime("%Y-%m-%d"),
        "date_posted": freshness.get('date_posted'),
        "freshness_verified": freshness.get('verified', False),
        "freshness_reason": freshness.get('reason'),
        "job_id": None,  # Will be assigned during import
        "status": "discovered",
        "score": None,
        "search_query": result.get('query', '')
    }


def generate_search_plan() -> List[Dict]:
    """Generate a list of all searches to run"""
    searches = []
    
    for platform, config in SEARCH_CONFIG.items():
        for query in config["queries"]:
            searches.append({
                "platform": platform,
                "query": query,
                "count": config["results_per_query"]
            })
    
    return searches


def save_search_results(jobs: List[Dict], output_file: str = None):
    """Save results to JSON file"""
    if not output_file:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_file = f"multi_site_jobs_{date_str}.json"
    
    with open(output_file, 'w') as f:
        json.dump(jobs, f, indent=2)
    
    print(f"Saved {len(jobs)} jobs to {output_file}")
    return output_file


def print_search_plan():
    """Print the search plan for manual execution"""
    searches = generate_search_plan()
    
    print("=" * 70)
    print("MULTI-SITE JOB SEARCH PLAN")
    print("=" * 70)
    print(f"Total searches: {len(searches)}")
    print(f"Rate limit: 1 req/sec (pace ~2-3 sec between searches)")
    print(f"Estimated time: ~{len(searches) * 3 // 60} minutes")
    print()
    
    for i, search in enumerate(searches, 1):
        print(f"{i}. [{search['platform'].upper()}]")
        print(f"   Query: {search['query']}")
        print(f"   Count: {search['count']}")
        print()
    
    print("=" * 70)
    print("EXECUTION OPTIONS:")
    print("=" * 70)
    print("1. Manual: Run each search manually via web_search tool")
    print("2. Automated: Use this script with web_search integration")
    print("3. Batch: Export queries to run via API with rate limiting")


def create_search_checklist():
    """Create a checklist file for manual execution"""
    searches = generate_search_plan()
    
    checklist = []
    checklist.append("# Multi-Site Job Search Checklist")
    checklist.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    checklist.append(f"# Total searches: {len(searches)}")
    checklist.append("")
    
    for i, search in enumerate(searches, 1):
        checklist.append(f"## {i}. {search['platform'].upper()}")
        checklist.append(f"- [ ] Query: `{search['query']}`")
        checklist.append(f"- [ ] Count: {search['count']}")
        checklist.append(f"- [ ] Jobs found: ___")
        checklist.append("")
    
    checklist.append("## Import Steps")
    checklist.append("- [ ] Run import script to add to tracker")
    checklist.append("- [ ] Score new jobs")
    checklist.append("- [ ] Generate resumes for 4.0+ matches")
    checklist.append("- [ ] Find LinkedIn contacts")
    
    filename = f"search_checklist_{datetime.now().strftime('%Y-%m-%d')}.md"
    filepath = f"/Users/ram/Projects/varun-job-search/{filename}"
    
    with open(filepath, 'w') as f:
        f.write('\n'.join(checklist))
    
    print(f"Checklist saved to: {filepath}")
    return filepath


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--checklist":
        create_search_checklist()
    else:
        print_search_plan()
        print("\nTo generate checklist: python3 multi_site_job_search.py --checklist")
