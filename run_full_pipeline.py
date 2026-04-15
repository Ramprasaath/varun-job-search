#!/usr/bin/env python3
"""
Unified Pipeline: LinkedIn Search → Tracker Import → Scoring → Resume Generation
"""

import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path

# Add skill path for imports
sys.path.insert(0, '/Users/ram/.openclaw/workspace/skills/varun-job-pipeline')

def run_linkedin_search():
    """Step 1: Run LinkedIn scraper"""
    print("=" * 70)
    print("STEP 1: Searching LinkedIn Jobs")
    print("=" * 70)
    
    result = subprocess.run(
        [sys.executable, "linkedin_scraper.py"],
        cwd="/Users/ram/varun-career-ops",
        capture_output=False
    )
    
    if result.returncode != 0:
        print("❌ LinkedIn search failed")
        return None
    
    # Find the output file
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = f"/Users/ram/varun-career-ops/linkedin_jobs_{date_str}.json"
    
    if Path(output_file).exists():
        with open(output_file) as f:
            jobs = json.load(f)
        print(f"✅ Found {len(jobs)} jobs")
        return output_file
    
    return None

def import_to_tracker(linkedin_file):
    """Step 2: Import to tracker"""
    print("\n" + "=" * 70)
    print("STEP 2: Importing to Tracker")
    print("=" * 70)
    
    result = subprocess.run(
        [sys.executable, "import_linkedin_jobs.py", linkedin_file],
        cwd="/Users/ram/varun-career-ops",
        capture_output=False
    )
    
    return result.returncode == 0

def run_scoring():
    """Step 3: Score un-evaluated jobs"""
    print("\n" + "=" * 70)
    print("STEP 3: Scoring New Jobs")
    print("=" * 70)
    print("Use the Streamlit app or ask me to score specific jobs")

def main():
    """Run full pipeline"""
    print("🚀 VARUN JOB PIPELINE - FULL RUN")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: LinkedIn Search
    linkedin_file = run_linkedin_search()
    if not linkedin_file:
        print("\n❌ Pipeline stopped at Step 1")
        return
    
    # Step 2: Import
    if not import_to_tracker(linkedin_file):
        print("\n❌ Pipeline stopped at Step 2")
        return
    
    # Step 3: Ready for scoring
    run_scoring()
    
    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Open Streamlit app: streamlit run streamlit-app/app.py")
    print("  2. Review newly imported jobs")
    print("  3. Ask me to score 4.0+ matches and generate tailored resumes")
    print("  4. I'll find LinkedIn contacts for top matches")

if __name__ == "__main__":
    main()
