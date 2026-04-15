#!/usr/bin/env python3
"""Quick test of LinkedIn scraper with debugging"""

from playwright.sync_api import sync_playwright
import time

print("🔍 Quick LinkedIn Test")

url = "https://www.linkedin.com/jobs/search?keywords=Scientist%20Analytical%20Chemistry&location=United%20States"

with sync_playwright() as p:
    print("Launching browser...")
    browser = p.chromium.launch(headless=True)
    print("✓ Browser launched")
    
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    print("✓ Page created")
    
    print(f"Navigating to: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print("✓ Page loaded")
    except Exception as e:
        print(f"❌ Navigation failed: {e}")
        browser.close()
        exit(1)
    
    time.sleep(3)
    
    # Check for common blocking indicators
    content = page.content()
    
    if "captcha" in content.lower() or "challenge" in content.lower():
        print("⚠️  LinkedIn is showing CAPTCHA/challenge")
    elif "sign in" in content.lower() and "join now" in content.lower():
        print("ℹ️  LinkedIn showing login prompt (expected for non-logged-in)")
    elif "job" in content.lower():
        print("✓ Job-related content found on page")
    else:
        print("? Unclear response from LinkedIn")
    
    # Try to find job listings
    jobs = page.query_selector_all("[data-job-id]")
    print(f"Found {len(jobs)} job cards with [data-job-id] selector")
    
    # Alternative selector
    job_links = page.query_selector_all("a[href*='/jobs/view/']")
    print(f"Found {len(job_links)} job links")
    
    # Save screenshot for debugging
    page.screenshot(path="/Users/ram/varun-career-ops/linkedin_test.png")
    print("✓ Screenshot saved to linkedin_test.png")
    
    browser.close()
    print("\n✅ Test complete")
