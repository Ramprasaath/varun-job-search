#!/usr/bin/env python3
"""Generate PDF from tailored resume"""

import json
import subprocess
import sys
from pathlib import Path

CAREER_OPS_DIR = Path("/Users/ram/Projects/varun-job-search")
RESUME_DIR = CAREER_OPS_DIR / "data" / "resume"
TEMPLATE_PATH = CAREER_OPS_DIR / "templates" / "cv-template.html"
OUTPUT_DIR = CAREER_OPS_DIR / "data" / "output"

def load_resume(version):
    path = RESUME_DIR / f"{version}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def build_resume_html(resume, company=""):
    """Build HTML from resume data using template"""
    with open(TEMPLATE_PATH) as f:
        tpl = f.read()
    
    name = resume.get("name", "")
    email = resume.get("email", "")
    phone = resume.get("phone", "")
    linkedin = resume.get("linkedin", "")
    linkedin_url = linkedin if linkedin.startswith("http") else f"https://{linkedin}"
    linkedin_display = linkedin.replace("https://", "").replace("http://", "")
    
    r = {
        "{{LANG}}": "en",
        "{{NAME}}": name,
        "{{PAGE_WIDTH}}": "8.5in",
        "{{EMAIL}}": email,
        "{{EMAIL_MAILTO}}": f"mailto:{email}",
        "{{PHONE}}": phone,
        "{{PHONE_TEL}}": f"tel:{phone}",
        "{{LINKEDIN_URL}}": linkedin_url,
        "{{LINKEDIN_DISPLAY}}": linkedin_display,
        "{{PORTFOLIO_URL}}": "#",
        "{{PORTFOLIO_DISPLAY}}": "",
        "{{LOCATION}}": "",
        "{{SECTION_SUMMARY}}": "PROFESSIONAL SUMMARY",
        "{{SECTION_COMPETENCIES}}": "CORE COMPETENCIES",
        "{{SECTION_EXPERIENCE}}": "WORK EXPERIENCE",
        "{{SECTION_PROJECTS}}": "KEY PROJECTS",
        "{{SECTION_EDUCATION}}": "EDUCATION",
        "{{SECTION_CERTIFICATIONS}}": "CERTIFICATIONS",
        "{{SECTION_SKILLS}}": "TECHNICAL SKILLS",
        "{{SUMMARY_TEXT}}": resume.get("summary", ""),
        "{{COMPETENCIES}}": "",
        "{{CERTIFICATIONS}}": "",
    }
    
    # Competencies
    comps = resume.get("competencies", [])
    if comps:
        r["{{COMPETENCIES}}"] = "\n".join(f'<span class="competency-tag">{c}</span>' for c in comps)
    
    # Experience
    exp_blocks = []
    for key in ["experience", "leadership"]:
        for exp in resume.get(key, []):
            bullets = "".join(f"<li>{b}</li>" for b in exp.get("bullets", []))
            exp_blocks.append(f'<div class="job"><div class="job-header"><span class="job-company">{exp.get("company", "")}</span><span class="job-period">{exp.get("period", "")}</span></div><div class="job-role">{exp.get("role", "")}</div><ul>{bullets}</ul></div>')
    r["{{EXPERIENCE}}"] = "\n".join(exp_blocks)
    
    # Projects
    proj_blocks = []
    for pr in resume.get("projects", []):
        badge = f'<span class="project-badge">{pr["badge"]}</span>' if pr.get("badge") else ""
        tech = f'<div class="project-tech">{pr["tech"]}</div>' if pr.get("tech") else ""
        proj_blocks.append(f'<div class="project"><div class="project-title">{pr.get("title", "")} {badge}</div><div class="project-desc">{pr.get("description", "")}</div>{tech}</div>')
    r["{{PROJECTS}}"] = "\n".join(proj_blocks)
    
    # Education
    edu_blocks = []
    for edu in resume.get("education", []):
        details = "<br>".join(edu.get("details", "").split("\n")) if edu.get("details") else ""
        edu_blocks.append(f'<div class="edu-item"><div class="edu-header"><span class="edu-title">{edu.get("degree", "")} - {edu.get("school", "")}</span><span class="edu-year">{edu.get("year", "")}</span></div><div class="edu-desc">{details}</div></div>')
    r["{{EDUCATION}}"] = "\n".join(edu_blocks)
    
    # Skills
    skill_blocks = []
    for cat, val in resume.get("skills", {}).items():
        skill_blocks.append(f'<div class="skill-row"><span class="skill-category">{cat}:</span> {val}</div>')
    r["{{SKILLS}}"] = "\n".join(skill_blocks)
    
    # Replace placeholders
    for k, v in r.items():
        tpl = tpl.replace(k, v)
    
    # Remove empty certifications section
    certs = resume.get("certifications", [])
    if not certs:
        tpl = tpl.replace('  <!-- CERTIFICATIONS -->\n  <div class="section avoid-break">\n    <div class="section-title">{{SECTION_CERTIFICATIONS}}</div>\n    {{CERTIFICATIONS}}\n  </div>\n\n', '')
    
    # Add extra sections
    extra = ""
    pubs = resume.get("publications", [])
    if pubs:
        extra += '<div class="section"><div class="section-title">JOURNAL PUBLICATIONS</div>\n'
        for i, p in enumerate(pubs, 1):
            extra += f'<div class="pub-entry">{i}. {p}</div>\n'
        extra += '</div>\n'
    
    confs = resume.get("conferences", [])
    if confs:
        extra += '<div class="section"><div class="section-title">CONFERENCE PRESENTATIONS</div>\n'
        for c in confs:
            extra += f'<div class="conf-entry">{c}</div>\n'
        extra += '</div>\n'
    
    honors = resume.get("honors", [])
    if honors:
        extra += '<div class="section"><div class="section-title">HONORS & AWARDS</div>\n'
        extra += '<div class="honors-entry">' + " &nbsp;|&nbsp; ".join(honors) + '</div>\n'
        extra += '</div>\n'
    
    if extra:
        tpl = tpl.replace("</div>\n</body>", extra + "\n</div>\n</body>")
    
    return tpl

def generate_pdf(resume_version, company_slug, job_title=""):
    """Generate PDF for a tailored resume"""
    resume = load_resume(resume_version)
    if not resume:
        print(f"Error: Could not load resume {resume_version}")
        return None
    
    # Build HTML
    html_content = build_resume_html(resume, company_slug)
    
    # Create temp HTML file
    tmp_html = f"/tmp/cv-tailored-{company_slug}.html"
    with open(tmp_html, "w") as f:
        f.write(html_content)
    
    # Generate PDF filename
    title_slug = job_title.lower().replace(" ", "-").replace("/", "-")[:40] if job_title else "position"
    pdf_name = f"cv-{company_slug}-{title_slug}-2026.pdf"
    pdf_path = OUTPUT_DIR / pdf_name
    
    # Generate PDF using Node script
    try:
        result = subprocess.run(
            ["node", str(CAREER_OPS_DIR / "generate-pdf.mjs"), tmp_html, str(pdf_path), "--format=letter"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(CAREER_OPS_DIR)
        )
        if result.returncode == 0:
            print(f"✅ PDF generated: {pdf_name}")
            return f"data/output/{pdf_name}"
        else:
            print(f"❌ PDF failed: {result.stderr[:300]}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 generate_resume_pdf.py <resume_version> <company_slug> [job_title]")
        print("Example: python3 generate_resume_pdf.py tailored_intertek intertek chemist")
        sys.exit(1)
    
    resume_version = sys.argv[1]
    company_slug = sys.argv[2]
    job_title = sys.argv[3] if len(sys.argv) > 3 else ""
    
    pdf_path = generate_pdf(resume_version, company_slug, job_title)
    if pdf_path:
        print(pdf_path)
