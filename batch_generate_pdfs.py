#!/usr/bin/env python3
"""Generate missing hosted PDFs for high-scoring jobs in the canonical tracker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from generate_resume_pdf import generate_pdf
from resume_renderer import BASE_DIR, RESUME_DIR, normalize_resume_version, resume_version_for_job

JOBS_PATH = BASE_DIR / "data" / "jobs.json"


def load_jobs() -> List[Dict[str, Any]]:
    with open(JOBS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_jobs(jobs: List[Dict[str, Any]]) -> None:
    with open(JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
        f.write("\n")


def needs_pdf(job: Dict[str, Any], min_score: float) -> bool:
    score = job.get("score")
    if not isinstance(score, (int, float)) or score < min_score:
        return False
    pdf_path = job.get("pdf_path")
    if not pdf_path:
        return True
    return not (BASE_DIR / pdf_path).exists()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-score", type=float, default=4.0, help="Minimum job score to generate PDFs for")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing PDFs too")
    args = parser.parse_args()

    jobs = load_jobs()
    targets = [
        job
        for job in jobs
        if isinstance(job.get("score"), (int, float))
        and job["score"] >= args.min_score
        and (args.overwrite or needs_pdf(job, args.min_score))
    ]
    targets.sort(key=lambda job: (job.get("score") or 0, job.get("date_found") or ""), reverse=True)

    print(f"Generating PDFs for {len(targets)} job(s) from {JOBS_PATH.relative_to(BASE_DIR)}")
    success_count = 0
    for job in targets:
        resume_version = normalize_resume_version(job.get("tailored_resume"))
        if not resume_version:
            candidate = resume_version_for_job(job)
            if not (RESUME_DIR / f"{candidate}.json").exists():
                print(f"  skipped: no tailored resume JSON found for suggested version {candidate}")
                continue
            resume_version = candidate
        print(f"- #{job.get('id')} {job.get('company')} — {job.get('title')} [{resume_version}]")
        pdf_path = generate_pdf(resume_version, job.get("company", ""), job.get("title", ""), overwrite=args.overwrite)
        if pdf_path:
            job["tailored_resume"] = resume_version
            job["pdf_path"] = pdf_path
            success_count += 1

    save_jobs(jobs)
    print(f"Generated {success_count}/{len(targets)} PDF(s)")
    return 0 if success_count == len(targets) else 1


if __name__ == "__main__":
    raise SystemExit(main())
