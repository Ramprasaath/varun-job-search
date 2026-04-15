#!/usr/bin/env python3
"""
LinkedIn Jobs Scraper for Varun's Pipeline
Searches LinkedIn Jobs and outputs results compatible with the existing jobs.json tracker
"""

import json
import time
import random
from datetime import datetime
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout


class LinkedInJobScraper:
    """Scraper for LinkedIn Jobs with safety features"""
    
    def __init__(self, headless: bool = True, delay_range: tuple = (3, 7)):
        self.headless = headless
        self.delay_range = delay_range  # Random delay between requests
        self.jobs_found = []
        
    def _random_delay(self):
        """Random delay to avoid detection"""
        time.sleep(random.uniform(*self.delay_range))
        
    def _safe_goto(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL with retries"""
        for attempt in range(max_retries):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self._random_delay()
                return True
            except PlaywrightTimeout:
                print(f"  Timeout on attempt {attempt + 1}, retrying...")
                time.sleep(5)
        return False
    
    def search_jobs(self, keywords: str, location: str = "United States", 
                    max_jobs: int = 50) -> List[Dict]:
        """
        Search LinkedIn Jobs
        
        Args:
            keywords: Job search keywords (e.g., "Scientist Analytical Chemistry")
            location: Location filter
            max_jobs: Maximum jobs to retrieve
            
        Returns:
            List of job dictionaries in tracker-compatible format
        """
        jobs = []
        
        # Build LinkedIn Jobs URL (simpler URL without auth-required filters)
        base_url = "https://www.linkedin.com/jobs/search"
        params = f"?keywords={keywords.replace(' ', '%20')}"
        params += f"&location={location.replace(' ', '%20')}"
        params += "&f_TPR=r604800"  # Past week (more results)
        
        search_url = base_url + params
        
        print(f"🔍 Searching LinkedIn Jobs: '{keywords}' in {location}")
        print(f"   URL: {search_url}")
        print(f"   Headless mode: {self.headless}")
        
        with sync_playwright() as p:
            print("  Launching browser...")
            browser = p.chromium.launch(headless=self.headless)
            print("  Browser launched")
            
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print("  Page created")
            
            # Navigate to search results
            print(f"  Navigating to URL...")
            if not self._safe_goto(page, search_url):
                print("❌ Failed to load search results")
                browser.close()
                return jobs
            
            print("  Page loaded, waiting for content...")
            # Wait for job cards to load
            try:
                page.wait_for_selector("[data-job-id]", timeout=15000)
                print("  Job cards selector found")
            except PlaywrightTimeout:
                print("  No job cards found on initial load, checking page content...")
                # Debug: save page content
                html_content = page.content()
                if "challenge" in html_content.lower() or "captcha" in html_content.lower():
                    print("  ⚠️  LinkedIn may be showing a CAPTCHA or challenge")
                elif "sign in" in html_content.lower():
                    print("  ⚠️  LinkedIn is requiring sign-in")
                else:
                    print(f"  Page content preview: {html_content[:500]}...")
            
            # Scroll and collect jobs
            previous_count = 0
            scroll_attempts = 0
            max_scrolls = min(max_jobs // 10, 20)  # Estimate 10 jobs per scroll
            
            while len(jobs) < max_jobs and scroll_attempts < max_scrolls:
                # Extract job cards currently visible
                job_cards = page.query_selector_all("[data-job-id]")
                
                for card in job_cards[len(jobs):max_jobs]:
                    try:
                        job = self._extract_job_data(card, page)
                        if job and job not in jobs:
                            jobs.append(job)
                            print(f"  ✓ Found: {job['title']} at {job['company']}")
                    except Exception as e:
                        print(f"  Error extracting job: {e}")
                        continue
                
                # Check if we found new jobs
                if len(jobs) == previous_count:
                    scroll_attempts += 1
                    if scroll_attempts >= 3:
                        print(f"  No new jobs after 3 scroll attempts, stopping")
                        break
                else:
                    scroll_attempts = 0
                    previous_count = len(jobs)
                
                # Scroll down to load more
                page.evaluate("window.scrollBy(0, 800)")
                self._random_delay()
            
            browser.close()
        
        print(f"\n✅ Total jobs found: {len(jobs)}")
        return jobs
    
    def _extract_job_data(self, card, page) -> Optional[Dict]:
        """Extract job data from a job card element"""
        try:
            # Click on job card to load details
            card.click()
        
            self._random_delay()
            
            # Extract basic info from the card
            title_elem = card.query_selector("strong")
            title = title_elem.inner_text() if title_elem else "Unknown Title"
            
            company_elem = card.query_selector("[class*='company-name']") or \
                          card.query_selector("a[href*='/company/']")
            company = company_elem.inner_text() if company_elem else "Unknown Company"
            
            location_elem = card.query_selector("[class*='metadata']") or \
                           card.query_selector("span:not([class])")
            location = location_elem.inner_text() if location_elem else "Unknown Location"
            
            # Get job ID from data attribute
            job_id = card.get_attribute("data-job-id") or ""
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}" if job_id else ""
            
            # Try to get description from detail panel
            description = ""
            try:
                desc_elem = page.query_selector("[class*='description']") or \
                           page.query_selector("#job-details")
                if desc_elem:
                    description = desc_elem.inner_text()
            except:
                pass
            
            # Create tracker-compatible job entry
            return {
                "source": "linkedin",
                "title": title.strip(),
                "company": company.strip(),
                "location": location.strip(),
                "url": job_url,
                "description": description[:2000],  # Limit description length
                "date_found": datetime.now().strftime("%Y-%m-%d"),
                "job_id": job_id,
                "status": "discovered",
                "score": None,  # To be evaluated
                "evaluation": None,
                "report_path": None,
                "pdf_path": None
            }
            
        except Exception as e:
            print(f"  Error parsing job card: {e}")
            return None


def run_pipeline_search(search_terms: List[str], location: str = "United States",
                        max_jobs_per_term: int = 25) -> List[Dict]:
    """
    Run searches for multiple terms and return unified results
    
    Args:
        search_terms: List of search queries
        location: Location filter
        max_jobs_per_term: Max jobs per search term
        
    Returns:
        Combined list of unique jobs
    """
    scraper = LinkedInJobScraper(headless=True)
    all_jobs = []
    seen_urls = set()
    
    for term in search_terms:
        print(f"\n{'='*60}")
        jobs = scraper.search_jobs(term, location, max_jobs_per_term)
        
        # Deduplicate
        for job in jobs:
            if job['url'] and job['url'] not in seen_urls:
                all_jobs.append(job)
                seen_urls.add(job['url'])
        
        # Cooldown between searches
        if term != search_terms[-1]:
            cooldown = random.randint(10, 20)
            print(f"\n  Cooling down for {cooldown}s before next search...")
            time.sleep(cooldown)
    
    return all_jobs


def export_to_tracker(jobs: List[Dict], tracker_path: str, 
                      output_path: str = None) -> str:
    """
    Export scraped jobs to a JSON file compatible with the tracker pipeline
    
    Args:
        jobs: List of scraped job dictionaries
        tracker_path: Path to existing jobs.json for ID offset
        output_path: Where to save the new jobs (default: linkedin_jobs_YYYYMMDD.json)
        
    Returns:
        Path to saved file
    """
    # Load existing tracker to get next ID
    try:
        with open(tracker_path, 'r') as f:
            existing = json.load(f)
            next_id = max([j.get('id', 0) for j in existing], default=0) + 1
    except:
        next_id = 1
    
    # Assign IDs and prepare for import
    for i, job in enumerate(jobs):
        job['id'] = next_id + i
    
    # Save to file
    if not output_path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = f"linkedin_jobs_{date_str}.json"
    
    with open(output_path, 'w') as f:
        json.dump(jobs, f, indent=2)
    
    print(f"\n💾 Saved {len(jobs)} jobs to: {output_path}")
    return output_path


if __name__ == "__main__":
    # Search configuration for Varun
    SEARCH_TERMS = [
        "Scientist Analytical Chemistry",
        "Analytical Development Scientist",
        "Scientist CMC Analytical",
        "Scientist Quality Control",
        "Formulation Scientist",
        "Materials Characterization Scientist"
    ]
    
    LOCATION = "United States"
    MAX_JOBS_PER_TERM = 20  # Conservative to avoid detection
    
    print("🚀 Starting LinkedIn Jobs Scraping Pipeline")
    print(f"   Terms: {len(SEARCH_TERMS)}")
    print(f"   Location: {LOCATION}")
    print(f"   Max jobs per term: {MAX_JOBS_PER_TERM}")
    
    # Run searches
    jobs = run_pipeline_search(SEARCH_TERMS, LOCATION, MAX_JOBS_PER_TERM)
    
    # Export for integration with tracker
    tracker_path = "/Users/ram/varun-career-ops/streamlit-app/data/jobs.json"
    output = export_to_tracker(jobs, tracker_path)
    
    print(f"\n✅ Pipeline complete!")
    print(f"   Found {len(jobs)} unique jobs")
    print(f"   Import file: {output}")
    print(f"\nNext steps:")
    print(f"  1. Review jobs in {output}")
    print(f"  2. Add them to your tracker for scoring")
    print(f"  3. I'll generate tailored resumes for 4.0+ matches")
