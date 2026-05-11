#!/usr/bin/env python3
"""Shared resume loading, rendering, and filename helpers for Varun's tracker."""

from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESUME_DIR = DATA_DIR / "resume"
TEMPLATE_PATH = BASE_DIR / "templates" / "cv-template.html"
OUTPUT_DIR = DATA_DIR / "output"


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = deep_merge(merged.get(key), value) if key in merged else value
        return merged
    return override if override is not None else base


def normalize_resume_version(value: Optional[str]) -> Optional[str]:
    """Accept plain versions or data/resume/*.json paths and return the version name."""
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    name = Path(raw).name
    return name[:-5] if name.endswith(".json") else name


def resume_paths(version: str = "base") -> Tuple[Path, Optional[Path]]:
    version = normalize_resume_version(version) or "base"
    if version == "base":
        return RESUME_DIR / "base_resume.json", RESUME_DIR / "base.json"
    return RESUME_DIR / f"{version}.json", None


def load_resume(version: str = "base") -> Dict[str, Any]:
    version = normalize_resume_version(version) or "base"
    primary, legacy = resume_paths(version)
    primary_data = load_json(primary, {})
    legacy_data = load_json(legacy, {}) if legacy else {}
    if version == "base":
        if primary_data and legacy_data:
            return deep_merge(primary_data, legacy_data)
        return primary_data or legacy_data or {}
    return primary_data or {}


def save_resume(data: Dict[str, Any], version: str = "base") -> None:
    version = normalize_resume_version(version) or "base"
    primary, legacy = resume_paths(version)
    save_json(primary, data)
    if legacy and legacy.exists():
        save_json(legacy, data)


def slugify(value: str, max_length: int = 80, separator: str = "-") -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", separator, normalized)
    normalized = normalized.strip(separator)
    if max_length and len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip(separator)
    return normalized or "item"


def resume_version_for_job(job: Dict[str, Any]) -> str:
    existing = normalize_resume_version(job.get("tailored_resume"))
    if existing:
        return existing
    company = slugify(job.get("company", "company"), separator="_")
    title = slugify(job.get("title", "role"), max_length=36, separator="_")
    return f"tailored_{company}_{title}"


def pdf_filename(company: str, job_title: str = "", year: Optional[int] = None) -> str:
    year = year or datetime.now().year
    company_slug = slugify(company, max_length=60)
    title_slug = slugify(job_title or "position", max_length=50)
    return f"cv-{company_slug}-{title_slug}-{year}.pdf"


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "#"
    return _e(value if value.startswith(("http://", "https://", "mailto:", "tel:")) else f"https://{value}")


def _remove_certifications_section(template: str) -> str:
    pattern = re.compile(
        r"\n\s*<!-- CERTIFICATIONS -->\s*"
        r"<div class=\"section avoid-break\">\s*"
        r"<div class=\"section-title\">\{\{SECTION_CERTIFICATIONS\}\}</div>\s*"
        r"\{\{CERTIFICATIONS\}\}\s*"
        r"</div>\s*",
        re.MULTILINE,
    )
    return pattern.sub("\n", template)


def build_resume_html(
    resume: Dict[str, Any],
    template_path: Path = TEMPLATE_PATH,
    page_width: str = "8.5in",
) -> str:
    """Build ATS-friendly resume HTML from structured resume JSON."""
    if not template_path.exists():
        return f"<html><body><h1>{_e(resume.get('name', ''))}</h1><p>Template missing.</p></body></html>"

    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    certs = resume.get("certifications", []) or []
    if not certs:
        template = _remove_certifications_section(template)

    linkedin = resume.get("linkedin", "") or ""
    linkedin_display = linkedin.replace("https://", "").replace("http://", "")

    replacements = {
        "{{LANG}}": "en",
        "{{NAME}}": _e(resume.get("name", "")),
        "{{PAGE_WIDTH}}": page_width,
        "{{EMAIL}}": _e(resume.get("email", "")),
        "{{EMAIL_MAILTO}}": _url(f"mailto:{resume.get('email', '')}" if resume.get("email") else ""),
        "{{PHONE}}": _e(resume.get("phone", "")),
        "{{PHONE_TEL}}": _url(f"tel:{resume.get('phone', '')}" if resume.get("phone") else ""),
        "{{LINKEDIN_URL}}": _url(linkedin),
        "{{LINKEDIN_DISPLAY}}": _e(linkedin_display),
        "{{PORTFOLIO_URL}}": "#",
        "{{PORTFOLIO_DISPLAY}}": "",
        "{{LOCATION}}": _e(resume.get("location", "")),
        "{{SECTION_SUMMARY}}": "PROFESSIONAL SUMMARY",
        "{{SECTION_COMPETENCIES}}": "CORE COMPETENCIES",
        "{{SECTION_EXPERIENCE}}": "WORK EXPERIENCE",
        "{{SECTION_PROJECTS}}": "KEY PROJECTS",
        "{{SECTION_EDUCATION}}": "EDUCATION",
        "{{SECTION_CERTIFICATIONS}}": "CERTIFICATIONS",
        "{{SECTION_SKILLS}}": "TECHNICAL SKILLS",
        "{{SUMMARY_TEXT}}": _e(resume.get("summary", "")),
        "{{COMPETENCIES}}": "",
        "{{CERTIFICATIONS}}": "",
    }

    if certs:
        replacements["{{CERTIFICATIONS}}"] = "\n".join(
            f'<div class="cert-item"><span class="cert-title">{_e(cert)}</span></div>' for cert in certs
        )

    competencies = resume.get("competencies", []) or []
    if competencies:
        replacements["{{COMPETENCIES}}"] = "\n".join(
            f'<span class="competency-tag">{_e(item)}</span>' for item in competencies
        )

    exp_blocks = []
    for key in ("experience", "leadership"):
        for exp in resume.get(key, []) or []:
            bullets = "".join(f"<li>{_e(bullet)}</li>" for bullet in exp.get("bullets", []) or [])
            exp_blocks.append(
                '<div class="job">'
                '<div class="job-header">'
                f'<span class="job-company">{_e(exp.get("company", ""))}</span>'
                f'<span class="job-period">{_e(exp.get("period", ""))}</span>'
                "</div>"
                f'<div class="job-role">{_e(exp.get("role", ""))}</div>'
                f"<ul>{bullets}</ul>"
                "</div>"
            )

    teaching = resume.get("teaching")
    if isinstance(teaching, dict) and any(teaching.get(k) for k in ("role", "school", "description")):
        description = teaching.get("description", "")
        bullets = f"<li>{_e(description)}</li>" if description else ""
        exp_blocks.append(
            '<div class="job">'
            '<div class="job-header">'
            f'<span class="job-company">{_e(teaching.get("school", ""))}</span>'
            f'<span class="job-period">{_e(teaching.get("period", ""))}</span>'
            "</div>"
            f'<div class="job-role">{_e(teaching.get("role", ""))}</div>'
            f"<ul>{bullets}</ul>"
            "</div>"
        )

    replacements["{{EXPERIENCE}}"] = "\n".join(exp_blocks)

    project_blocks = []
    for project in resume.get("projects", []) or []:
        badge = f'<span class="project-badge">{_e(project.get("badge"))}</span>' if project.get("badge") else ""
        tech = f'<div class="project-tech">{_e(project.get("tech"))}</div>' if project.get("tech") else ""
        project_blocks.append(
            '<div class="project">'
            f'<div class="project-title">{_e(project.get("title", ""))} {badge}</div>'
            f'<div class="project-desc">{_e(project.get("description", ""))}</div>'
            f"{tech}"
            "</div>"
        )
    replacements["{{PROJECTS}}"] = "\n".join(project_blocks)

    edu_blocks = []
    for edu in resume.get("education", []) or []:
        details = "<br>".join(_e(edu.get("details", "")).split("\n")) if edu.get("details") else ""
        edu_blocks.append(
            '<div class="edu-item">'
            '<div class="edu-header">'
            f'<span class="edu-title">{_e(edu.get("degree", ""))} - {_e(edu.get("school", ""))}</span>'
            f'<span class="edu-year">{_e(edu.get("year", ""))}</span>'
            "</div>"
            f'<div class="edu-desc">{details}</div>'
            "</div>"
        )
    replacements["{{EDUCATION}}"] = "\n".join(edu_blocks)

    skill_blocks = []
    for category, value in (resume.get("skills", {}) or {}).items():
        skill_blocks.append(f'<div class="skill-row"><span class="skill-category">{_e(category)}:</span> {_e(value)}</div>')
    replacements["{{SKILLS}}"] = "\n".join(skill_blocks)

    for key, value in replacements.items():
        template = template.replace(key, value)

    extra = ""
    publications = resume.get("publications", []) or []
    if publications:
        extra += '<div class="section"><div class="section-title">JOURNAL PUBLICATIONS</div>\n'
        for idx, publication in enumerate(publications, 1):
            extra += f'<div class="pub-entry">{idx}. {_e(publication)}</div>\n'
        extra += "</div>\n"

    conferences = resume.get("conferences", []) or []
    if conferences:
        extra += '<div class="section"><div class="section-title">CONFERENCE PRESENTATIONS</div>\n'
        for conference in conferences:
            extra += f'<div class="conf-entry">{_e(conference)}</div>\n'
        extra += "</div>\n"

    honors = resume.get("honors", []) or []
    if honors:
        extra += '<div class="section"><div class="section-title">HONORS &amp; AWARDS</div>\n'
        extra += '<div class="honors-entry">' + " &nbsp;|&nbsp; ".join(_e(honor) for honor in honors) + "</div>\n"
        extra += "</div>\n"

    if extra:
        template = template.replace("</div>\n</body>", extra + "\n</div>\n</body>")
    return template
