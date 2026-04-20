#!/usr/bin/env python3
"""
LinkedIn Jobs Scraper v2 - Extracts from HTML even with login modal
"""

import json
import time
import random
import re
from datetime import datetime
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright

from job_freshness import assess_job_freshness


class LinkedInJobScraper:
    """Scraper for LinkedIn Jobs - works around login modal"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.jobs_found = []
        
    def search_jobs(self, keywords: str, location: str = "United States", 
                    max_jobs: int = 50) -> List[Dict]:
        """Search LinkedIn Jobs and extract from HTML"""
        jobs = []
        
        # Build URL
        base_url = "https://www.linkedin.com/jobs/search"
        params = f"?keywords={keywords.replace(' ', '%20')}"
        params += f"&location={location.replace(' ', '%20')}"
        params += "&f_TPR=r604800"  # Past week
        
        search_url = base_url + params
        
        print(f"🔍 Searching: '{keywords}'")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            try:
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                time.sleep(3)  # Let content load
                
                # Get page HTML
                html = page.content()
                
                # Extract jobs from HTML using regex and parsing
                jobs = self._extract_jobs_from_html(html, keywords)
                
                print(f"  ✓ Found {len(jobs)} jobs")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
            
            browser.close()
        
        return jobs[:max_jobs]
    
    def _extract_jobs_from_html(self, html: str, search_term: str) -> List[Dict]:
        """Extract job data from HTML content"""
        jobs = []
        
        # Pattern 1: Look for job listing data in script tags (JSON-LD)
        json_ld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        json_ld_matches = re.findall(json_ld_pattern, html, re.DOTALL)
        
        for match in json_ld_matches:
            try:
                data = json.loads(match.strip())
                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    job = self._parse_jobposting(data, search_term)
                    if job:
                        jobs.append(job)
            except:
                pass
        
        # Pattern 2: Look for job cards in HTML structure
        # LinkedIn uses data-job-id attributes
        job_card_pattern = r'data-job-id="(\d+)"[^>]*>.*?<a[^>]*href="(/jobs/view/[^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>'
        matches = re.findall(job_card_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for job_id, href, title in matches:
            if not any(j.get('job_id') == job_id for j in jobs):
                job_url = f"https://www.linkedin.com{href}" if href.startswith('/') else href
                freshness = assess_job_freshness(title=title, url=job_url, source="linkedin")
                job = {
                    "source": "linkedin",
                    "title": title.strip(),
                    "company": "Unknown",  # Will try to extract better
                    "location": "Unknown",
                    "url": job_url,
                    "description": "",
                    "date_found": datetime.now().strftime("%Y-%m-%d"),
                    "date_posted": freshness.get("date_posted"),
                    "freshness_verified": freshness.get("verified", False),
                    "freshness_reason": freshness.get("reason"),
                    "job_id": job_id,
                    "status": "discovered",
                    "score": None,
                    "search_term": search_term
                }
                jobs.append(job)
        
        # Pattern 3: Parse the visible job list HTML
        # Look for job title/company/location patterns
        job_list_pattern = r'<a[^>]*href="(/jobs/view/\d+)"[^>]*>.*?<span[^>]*class="[^"]*job-title[^"]*"[^>]*>([^<]+)</span>.*?<span[^>]*class="[^"]*company-name[^"]*"[^>]*>([^<]+)</span>'
        list_matches = re.findall(job_list_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for href, title, company in list_matches:
            job_id = re.search(r'/jobs/view/(\d+)', href)
            job_id = job_id.group(1) if job_id else ""
            
            if job_id and not any(j.get('job_id') == job_id for j in jobs):
                job_url = f"https://www.linkedin.com{href}"
                freshness = assess_job_freshness(title=title, url=job_url, source="linkedin")
                job = {
                    "source": "linkedin",
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": "Unknown",
                    "url": job_url,
                    "description": "",
                    "date_found": datetime.now().strftime("%Y-%m-%d"),
                    "date_posted": freshness.get("date_posted"),
                    "freshness_verified": freshness.get("verified", False),
                    "freshness_reason": freshness.get("reason"),
                    "job_id": job_id,
                    "status": "discovered",
                    "score": None,
                    "search_term": search_term
                }
                jobs.append(job)
        
        return jobs
    
    def _parse_jobposting(self, data: dict, search_term: str) -> Optional[Dict]:
        """Parse JSON-LD JobPosting data"""
        try:
            job_id = ""
            url = data.get('url', '')
            if url:
                match = re.search(r'/jobs/view/(\d+)', url)
                if match:
                    job_id = match.group(1)
            
            freshness = assess_job_freshness(
                title=data.get('title', 'Unknown'),
                description=data.get('description', ''),
                url=url,
                source='linkedin',
                explicit_date_posted=data.get('datePosted'),
            )
            return {
                "source": "linkedin",
                "title": data.get('title', 'Unknown'),
                "company": data.get('hiringOrganization', {}).get('name', 'Unknown'),
                "location": data.get('jobLocation', {}).get('address', {}).get('addressLocality', 'Unknown'),
                "url": url,
                "description": data.get('description', '')[:2000],
                "date_found": datetime.now().strftime("%Y-%m-%d"),
                "date_posted": freshness.get("date_posted"),
                "freshness_verified": freshness.get("verified", False),
                "freshness_reason": freshness.get("reason"),
                "job_id": job_id,
                "status": "discovered",
                "score": None,
                "search_term": search_term
            }
        except:
            return None


def run_pipeline_search(search_terms: List[str], location: str = "United States",
                        max_jobs_per_term: int = 20) -> List[Dict]:
    """Run searches for multiple terms"""
    scraper = LinkedInJobScraper(headless=True)
    all_jobs = []
    seen_urls = set()
    
    for term in search_terms:
        print(f"\n{'='*60}")
        jobs = scraper.search_jobs(term, location, max_jobs_per_term)
        
        for job in jobs:
            if job['url'] and job['url'] not in seen_urls:
                all_jobs.append(job)
                seen_urls.add(job['url'])
                print(f"  ✓ {job['title']} @ {job['company']}")
        
        time.sleep(random.randint(5, 10))  # Cooldown
    
    return all_jobs


def export_to_tracker(jobs: List[Dict], tracker_path: str, 
                      output_path: str = None) -> str:
    """Export scraped jobs to tracker-compatible JSON"""
    try:
        with open(tracker_path, 'r') as f:
            existing = json.load(f)
            next_id = max([j.get('id', 0) for j in existing], default=0) + 1
    except:
        next_id = 1
    
    for i, job in enumerate(jobs):
        job['id'] = next_id + i
        job['archetype'] = "Analytical / Quality Scientist"
        job['applied_date'] = None
        job['follow_up_date'] = None
        job['notes'] = f"LinkedIn search: {job.get('search_term', 'unknown')}"
        job['tailored_resume'] = None
        job['evaluation'] = None
        job['report_path'] = None
        job['pdf_path'] = None
    
    if not output_path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = f"linkedin_jobs_{date_str}.json"
    
    with open(output_path, 'w') as f:
        json.dump(jobs, f, indent=2)
    
    print(f"\n💾 Saved {len(jobs)} jobs to: {output_path}")
    return output_path


if __name__ == "__main__":
    SEARCH_TERMS = [
        "Scientist Analytical Chemistry",
        "Analytical Development Scientist",
        "Scientist CMC",
    ]
    
    print("🚀 LinkedIn Jobs Scraper v2")
    print("   (Extracts from HTML, works around login modal)")
    
    jobs = run_pipeline_search(SEARCH_TERMS, "United States", 15)
    
    tracker_path = "/Users/ram/Projects/varun-job-search/data/jobs.json"
    output = export_to_tracker(jobs, tracker_path)
    
    print(f"\n✅ Done! Found {len(jobs)} unique jobs")
    print(f"   File: {output}")
