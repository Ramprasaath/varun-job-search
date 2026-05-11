#!/usr/bin/env python3
"""Generate a hosted PDF from a base or tailored resume JSON."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from resume_renderer import BASE_DIR, OUTPUT_DIR, build_resume_html, load_resume, pdf_filename, slugify


def generate_pdf(resume_version: str, company: str, job_title: str = "", overwrite: bool = True) -> str | None:
    """Generate a PDF for a structured resume version and return its repo-relative path."""
    resume = load_resume(resume_version)
    if not resume:
        print(f"Error: could not load resume version '{resume_version}'", file=sys.stderr)
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_name = pdf_filename(company or slugify(resume_version), job_title)
    pdf_path = OUTPUT_DIR / pdf_name
    if pdf_path.exists() and not overwrite:
        print(f"PDF already exists: {pdf_name}")
        return f"data/output/{pdf_name}"

    html_content = build_resume_html(resume)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=f"-{slugify(company or resume_version)}.html",
        delete=False,
    ) as tmp:
        tmp.write(html_content)
        tmp_html = Path(tmp.name)

    try:
        result = subprocess.run(
            ["node", str(BASE_DIR / "generate-pdf.mjs"), str(tmp_html), str(pdf_path), "--format=letter"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BASE_DIR),
        )
    finally:
        tmp_html.unlink(missing_ok=True)

    if result.returncode == 0:
        print(f"PDF generated: {pdf_name}")
        return f"data/output/{pdf_name}"

    print(f"PDF failed for {resume_version}: {result.stderr[:500]}", file=sys.stderr)
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python3 generate_resume_pdf.py <resume_version> <company> [job_title]")
        print('Example: python3 generate_resume_pdf.py tailored_intertek intertek "Vibrational Spectroscopy Chemist"')
        return 1

    resume_version = sys.argv[1]
    company = sys.argv[2]
    job_title = sys.argv[3] if len(sys.argv) > 3 else ""
    pdf_path = generate_pdf(resume_version, company, job_title)
    if not pdf_path:
        return 1
    print(pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
