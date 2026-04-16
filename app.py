import streamlit as st
import json, os, datetime, subprocess
from pathlib import Path

st.set_page_config(page_title="Varun's Job Pipeline", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CAREER_OPS_DIR = BASE_DIR
RESUME_DIR = DATA_DIR / "resume"

def lj(path, default=None):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return default if default is not None else []

def sj(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2, ensure_ascii=False)

load_jobs = lambda: lj(DATA_DIR / "jobs.json", [])
save_jobs = lambda d: sj(DATA_DIR / "jobs.json", d)
load_contacts = lambda: lj(DATA_DIR / "contacts.json", [])
save_contacts = lambda d: sj(DATA_DIR / "contacts.json", d)
load_resume = lambda v="base": lj(RESUME_DIR / f"{v}.json", {})
save_resume = lambda d, v="base": sj(RESUME_DIR / f"{v}.json", d)
def nid(items): return max((i.get("id",0) for i in items), default=0) + 1

STATUS = ["discovered","evaluated","interested","applying","applied","interviewing","offer","rejected","withdrawn"]
S_EMOJI = {"discovered":"⚪","evaluated":"🟡","interested":"🟠","applying":"🔵","applied":"🔷","interviewing":"🟢","offer":"🎉","rejected":"🔴","withdrawn":"⚫"}
CT_STAT = ["not_contacted","request_sent","responded","call_scheduled","met"]
CT_TYPES = {"hiring_manager":"👔 Hiring Mgr","recruiter":"🔍 Recruiter","peer":"🤝 Peer","ceo":"🏢 CEO"}

st.markdown("""<style>
.apply-btn{display:inline-block;background:#2563EB;color:#fff!important;padding:6px 16px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px}
.apply-btn:hover{background:#1D4ED8}
</style>""", unsafe_allow_html=True)

# --- Resume HTML builder ---
def _build_resume_html(resume, company=""):
    template_path = CAREER_OPS_DIR / "templates" / "cv-template.html"
    if not template_path.exists():
        return f"<html><body><h1>{resume.get('name','')}</h1><p>Template missing.</p></body></html>"
    with open(template_path) as f: tpl = f.read()
    name,email,phone = resume.get("name",""), resume.get("email",""), resume.get("phone","")
    linkedin = resume.get("linkedin","")
    linkedin_url = linkedin if linkedin.startswith("http") else f"https://{linkedin}"
    linkedin_display = linkedin.replace("https://","").replace("http://","")

    r = {
        "{{LANG}}":"en","{{NAME}}":name,"{{PAGE_WIDTH}}":"8.5in",
        "{{EMAIL}}":email,"{{EMAIL_MAILTO}}":f"mailto:{email}",
        "{{PHONE}}":phone,"{{PHONE_TEL}}":f"tel:{phone}",
        "{{LINKEDIN_URL}}":linkedin_url,"{{LINKEDIN_DISPLAY}}":linkedin_display,
        "{{PORTFOLIO_URL}}":"#","{{PORTFOLIO_DISPLAY}}":"","{{LOCATION}}":"",
        "{{SECTION_SUMMARY}}":"PROFESSIONAL SUMMARY","{{SECTION_COMPETENCIES}}":"CORE COMPETENCIES",
        "{{SECTION_EXPERIENCE}}":"WORK EXPERIENCE","{{SECTION_PROJECTS}}":"KEY PROJECTS",
        "{{SECTION_EDUCATION}}":"EDUCATION","{{SECTION_CERTIFICATIONS}}":"CERTIFICATIONS",
        "{{SECTION_SKILLS}}":"TECHNICAL SKILLS","{{SUMMARY_TEXT}}":resume.get("summary",""),
        "{{COMPETENCIES}}":"","{{CERTIFICATIONS}}":"",
    }

    certs = resume.get("certifications",[])
    if certs:
        r["{{CERTIFICATIONS}}"] = "\n".join(f'<div class="cert-item"><span class="cert-title">{c}</span></div>' for c in certs)

    comps = resume.get("competencies",[])
    if comps: r["{{COMPETENCIES}}"] = "\n".join(f'<span class="competency-tag">{c}</span>' for c in comps)

    exp_blocks = []
    for key in ["experience","leadership"]:
        for exp in resume.get(key,[]):
            bullets = "".join(f"<li>{b}</li>" for b in exp.get("bullets",[]))
            exp_blocks.append(f'<div class="job"><div class="job-header"><span class="job-company">{exp.get("company","")}</span><span class="job-period">{exp.get("period","")}</span></div><div class="job-role">{exp.get("role","")}</div><ul>{bullets}</ul></div>')
    r["{{EXPERIENCE}}"] = "\n".join(exp_blocks)

    proj_blocks = []
    for pr in resume.get("projects",[]):
        badge = f'<span class="project-badge">{pr["badge"]}</span>' if pr.get("badge") else ""
        tech = f'<div class="project-tech">{pr["tech"]}</div>' if pr.get("tech") else ""
        proj_blocks.append(f'<div class="project"><div class="project-title">{pr.get("title","")} {badge}</div><div class="project-desc">{pr.get("description","")}</div>{tech}</div>')
    r["{{PROJECTS}}"] = "\n".join(proj_blocks)

    edu_blocks = []
    for edu in resume.get("education",[]):
        details = "<br>".join(edu.get("details","").split("\n")) if edu.get("details") else ""
        edu_blocks.append(f'<div class="edu-item"><div class="edu-header"><span class="edu-title">{edu.get("degree","")} - {edu.get("school","")}</span><span class="edu-year">{edu.get("year","")}</span></div><div class="edu-desc">{details}</div></div>')
    r["{{EDUCATION}}"] = "\n".join(edu_blocks)

    skill_blocks = []
    for cat,val in resume.get("skills",{}).items():
        skill_blocks.append(f'<div class="skill-row"><span class="skill-category">{cat}:</span> {val}</div>')
    r["{{SKILLS}}"] = "\n".join(skill_blocks)

    for k,v in r.items(): tpl = tpl.replace(k,v)

    # Remove empty certifications section
    if not certs:
        tpl = tpl.replace('  <!-- CERTIFICATIONS -->\n  <div class="section avoid-break">\n    <div class="section-title">{{SECTION_CERTIFICATIONS}}</div>\n    {{CERTIFICATIONS}}\n  </div>\n\n', '')

    extra = ""
    pubs = resume.get("publications",[])
    if pubs:
        extra += '<div class="section"><div class="section-title">JOURNAL PUBLICATIONS</div>\n'
        for i,p in enumerate(pubs,1): extra += f'<div class="pub-entry">{i}. {p}</div>\n'
        extra += '</div>\n'
    confs = resume.get("conferences",[])
    if confs:
        extra += '<div class="section"><div class="section-title">CONFERENCE PRESENTATIONS</div>\n'
        for c in confs: extra += f'<div class="conf-entry">{c}</div>\n'
        extra += '</div>\n'
    honors = resume.get("honors",[])
    if honors:
        extra += '<div class="section"><div class="section-title">HONORS & AWARDS</div>\n'
        extra += '<div class="honors-entry">' + " &nbsp;|&nbsp; ".join(honors) + '</div>\n'
        extra += '</div>\n'
    if extra: tpl = tpl.replace("</div>\n</body>", extra + "\n</div>\n</body>")
    return tpl

# ================================================================
st.markdown("# 🎯 Varun's Job Pipeline")
tab_tracker, tab_resume = st.tabs(["📋 Tracker", "📝 Resume Builder"])

# ================================================================
# TRACKER
# ================================================================
with tab_tracker:
    jobs = load_jobs()
    contacts = load_contacts()

    # -- Metrics --
    if jobs:
        sc = {}
        for j in jobs: sc[j.get("status","discovered")] = sc.get(j.get("status","discovered"),0)+1
        ev = [j for j in jobs if j.get("score")]
        avg = sum(j["score"] for j in ev)/len(ev) if ev else 0
        high_score = len([j for j in jobs if j.get("score") and j["score"] >= 4.0])
        new_jobs = len([j for j in jobs if j.get("status") == "discovered"])
        not_applied = len([j for j in jobs if j.get("status") not in ("applied", "interviewing", "offer", "rejected")])
        od = [j for j in jobs if j.get("follow_up_date") and j["follow_up_date"]<=datetime.date.today().isoformat() and j["status"] in("applied","interviewing")]
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Total",len(jobs)); c2.metric("Avg",f"{avg:.1f}"); c3.metric("⭐ 4.0+",high_score)
        c4.metric("🆕 New",new_jobs); c5.metric("📋 To Apply",not_applied); c6.metric("⚠️ Due",len(od))
    else:
        st.info("Add your first job below!"); od=[]

    # -- Add job --
    with st.expander("➕ Add New Job"):
        with st.form("add_j"):
            a1,a2,a3 = st.columns(3)
            with a1: a_url=st.text_input("URL*", placeholder="https://...")
            with a2: a_co=st.text_input("Company*")
            with a3: a_ti=st.text_input("Title*")
            a1b,a2b = st.columns(2)
            with a1b: a_loc=st.text_input("Location"); a_sc=st.number_input("Score",0.0,5.0,0.0,0.1)
            with a2b: a_no=st.text_area("Notes", height=60)
            if st.form_submit_button("Add", type="primary"):
                if a_url and a_co and a_ti:
                    jobs.append({"id":nid(jobs),"url":a_url,"company":a_co,"title":a_ti,"location":a_loc,
                        "date_found":datetime.date.today().isoformat(),"score":a_sc if a_sc>0 else None,
                        "status":"discovered","report_path":None,"pdf_path":None,"applied_date":None,
                        "follow_up_date":None,"tailored_resume":None,"notes":a_no,"evaluation":None,"archetype":None})
                    save_jobs(jobs); st.success(f"✅ Added {a_co}"); st.rerun()
                else: st.error("URL, Company, Title required")

    st.markdown("---")

    # -- Overdue alerts --
    if od:
        for j in od:
            d=(datetime.date.today()-datetime.date.fromisoformat(j["follow_up_date"])).days
            st.warning(f"⚠️ **{j['company']}** — {j['title']} — follow-up **{d} days overdue**")
        st.markdown("---")

    # -- Sorting & Filtering Controls --
    if jobs:
        st.markdown("### 🔍 Filter & Sort")
        f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
        
        with f1:
            sort_by = st.selectbox("Sort by", [
                "Score (High to Low)",
                "Date Found (Newest)",
                "Date Found (Oldest)",
                "Company (A-Z)",
                "Status"
            ], index=0)
        
        with f2:
            filter_status = st.multiselect("Status", 
                ["discovered", "evaluated", "interested", "applying", "applied", "interviewing", "offer"],
                default=["discovered", "evaluated", "interested", "applying"],
                placeholder="Select statuses..."
            )
        
        with f3:
            min_score = st.slider("Min Score", 0.0, 5.0, 0.0, 0.5)
        
        with f4:
            show_recent_only = st.checkbox("Recent only (7 days)", value=False)
            show_high_priority = st.checkbox("4.0+ only", value=False)
        
        st.markdown("---")
    
    # -- Simple native tracker --
    if jobs:
        import pandas as pd

        st.markdown("### 📊 Tracker")
        
        # Apply filters
        filtered_jobs = jobs.copy()
        
        # Filter by status
        if filter_status:
            filtered_jobs = [j for j in filtered_jobs if j.get("status", "discovered") in filter_status]
        
        # Filter by minimum score
        if min_score > 0:
            filtered_jobs = [j for j in filtered_jobs if (j.get("score") or 0) >= min_score]
        
        # Filter by recent only
        if show_recent_only:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            filtered_jobs = [j for j in filtered_jobs if j.get("date_found", "") >= cutoff]
        
        # Filter by high priority only
        if show_high_priority:
            filtered_jobs = [j for j in filtered_jobs if (j.get("score") or 0) >= 4.0]
        
        # Apply sorting
        if sort_by == "Score (High to Low)":
            filtered_jobs.sort(key=lambda x: (x.get("score") or 0, x.get("date_found", "")), reverse=True)
        elif sort_by == "Date Found (Newest)":
            filtered_jobs.sort(key=lambda x: (x.get("date_found", ""), x.get("score") or 0), reverse=True)
        elif sort_by == "Date Found (Oldest)":
            filtered_jobs.sort(key=lambda x: x.get("date_found", ""))
        elif sort_by == "Company (A-Z)":
            filtered_jobs.sort(key=lambda x: x.get("company", "").lower())
        elif sort_by == "Status":
            filtered_jobs.sort(key=lambda x: x.get("status", "discovered"))
        
        # Show filter summary
        st.caption(f"Showing {len(filtered_jobs)} of {len(jobs)} jobs")
        
        # Build display dataframe with index as job ID
        rows = []
        for j in filtered_jobs:
            applied = j.get("applied_date") if j.get("applied_date") else ""
            followup = j.get("follow_up_date") if j.get("follow_up_date") else ""
            has_pdf = "📄" if j.get("pdf_path") and (CAREER_OPS_DIR / j["pdf_path"]).exists() else ""
            rows.append({
                "ID": j["id"],
                "Company": j.get("company",""),
                "Role": j.get("title","")[:50],
                "Score": round(j.get("score") or 0, 1),
                "Status": j.get("status","discovered"),
                "Location": j.get("location",""),
                "Found": j.get("date_found",""),
                "Applied": applied,
                "Follow": followup,
                "PDF": has_pdf
            })
        df = pd.DataFrame(rows)

        # Use st.data_editor for editable table
        edited_df = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Score": st.column_config.NumberColumn("Score", format="%.1f", disabled=True),
                "Status": st.column_config.SelectboxColumn("Status", options=STATUS),
                "Applied": st.column_config.TextColumn("Applied"),
                "Follow": st.column_config.TextColumn("Follow-up"),
                "PDF": st.column_config.Column("PDF", disabled=True)
            },
            key="job_editor"
        )
        
        # Save changes back to jobs
        if edited_df is not None:
            changed = False
            for _, row in edited_df.iterrows():
                job = next((j for j in jobs if j["id"] == row["ID"]), None)
                if job:
                    if job.get("status") != row["Status"]:
                        job["status"] = row["Status"]
                        changed = True
                    if job.get("applied_date") != row["Applied"] and row["Applied"]:
                        job["applied_date"] = row["Applied"]
                        changed = True
                    if job.get("follow_up_date") != row["Follow"] and row["Follow"]:
                        job["follow_up_date"] = row["Follow"]
                        changed = True
            if changed:
                save_jobs(jobs)
        
        # Job selector with button-style links
        st.markdown("#### Select Job to View Details")
        cols = st.columns(4)
        for idx, job in enumerate(filtered_jobs[:8]):  # Show first 8 as buttons
            with cols[idx % 4]:
                if st.button(f"{job['company'][:15]}", key=f"btn_{job['id']}"):
                    st.session_state["selected_job_id"] = job["id"]
        
        # Or use dropdown for all
        job_options = {f"{j['company']} - {j['title'][:30]}": j['id'] for j in filtered_jobs}
        selected_label = st.selectbox("Or select from full list:", [""] + list(job_options.keys()), key="job_dropdown")
        if selected_label:
            st.session_state["selected_job_id"] = job_options[selected_label]
        
        # Get selected job
        if st.session_state.get("selected_job_id"):
            j = next((x for x in jobs if x["id"]==st.session_state["selected_job_id"]), None)
        else:
            j = None

        # Export CSV
        csv_df = pd.DataFrame([{
            "Company": j.get("company",""),
            "Title": j.get("title",""),
            "Score": j.get("score"),
            "Status": j.get("status","discovered"),
            "Location": j.get("location",""),
            "Date_Found": j.get("date_found",""),
            "Applied_Date": j.get("applied_date",""),
            "Follow_Up_Date": j.get("follow_up_date",""),
            "Notes": j.get("notes",""),
            "URL": j.get("url","")
        } for j in filtered_jobs])
        csv = csv_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Export CSV", csv, "varun-job-tracker.csv", "text/csv")
    else:
        j = None

    if not j and st.session_state.get("selected_job_id"):
        j = next((x for x in jobs if x["id"]==st.session_state["selected_job_id"]), None) if jobs else None

    # -- Job detail panel --
    if j:
        jcts = [c for c in contacts if c.get("job_id")==j["id"]]
        em = S_EMOJI.get(j.get("status","discovered"),"⚪")
        sc_str = f"⭐{j['score']:.1f}" if j.get("score") else ""

        st.markdown(f"## {em} {j['company']} — {j['title']} {sc_str}")

        # Quick Actions
        c1, c2, c3 = st.columns([1,1,2])
        with c1:
            if j.get("url"):
                st.link_button("🔗 Apply / View Posting", j["url"])
        with c2:
            if j.get("pdf_path"):
                pdf_path = CAREER_OPS_DIR / j["pdf_path"]
                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button("📄 Download Resume", pdf_bytes, pdf_path.name, "application/pdf", key=f"dlr_{j['id']}")
        
        st.caption(f"📍 {j.get('location','—')} | 📅 Found: {j.get('date_found','—')}")
        
        # Edit fields
        st.markdown("#### Update Job")
        ed1, ed2, ed3, ed4 = st.columns([1.5,1.5,1.5,1])
        with ed1:
            ns = st.selectbox("Status", STATUS, index=STATUS.index(j.get("status","discovered")), key=f"s_{j['id']}")
        with ed2:
            na = st.date_input("Applied", value=datetime.date.fromisoformat(j["applied_date"]) if j.get("applied_date") else None, key=f"ja_{j['id']}")
        with ed3:
            nf = st.date_input("Follow-up", value=datetime.date.fromisoformat(j["follow_up_date"]) if j.get("follow_up_date") else datetime.date.today()+datetime.timedelta(days=7), key=f"jf_{j['id']}")
        with ed4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Save", key=f"sv_{j['id']}"):
                j["status"] = ns
                j["applied_date"] = str(na) if na else None
                j["follow_up_date"] = str(nf) if nf else None
                save_jobs(jobs)
                st.success("Saved!")
                st.rerun()

        st.markdown("---")
        et,ct,rt,nt = st.tabs(["📊 Eval",f"👥 Contacts ({len(jcts)})","📝 Resume","📋 Notes"])

        # EVAL
        with et:
            if j.get("evaluation"):
                ev=j["evaluation"]
                e1,e2,e3,e4=st.columns(4)
                e1.metric("CV Match",f"{ev.get('cv_match','—')}/5")
                e2.metric("Fit",f"{ev.get('north_star','—')}/5")
                e3.metric("Comp",f"{ev.get('comp','—')}/5")
                e4.metric("Legit",ev.get("legitimacy","—"))
                if ev.get("recommendation"): st.info(f"💡 {ev['recommendation']}")
                s1,s2=st.columns(2)
                with s1:
                    if ev.get("strengths"):
                        st.markdown("**Strengths:**")
                        for s in ev["strengths"]: st.markdown(f"- ✅ {s}")
                with s2:
                    if ev.get("gaps"):
                        st.markdown("**Gaps:**")
                        for g in ev["gaps"]: st.markdown(f"- ⚠️ {g}")
            else:
                st.markdown("*Not yet evaluated.*")
            if j.get("report_path") and os.path.exists(CAREER_OPS_DIR/j["report_path"]):
                with open(CAREER_OPS_DIR/j["report_path"]) as f:
                    with st.expander("📄 Full Report"): st.markdown(f.read())

        # CONTACTS
        with ct:
            for c in jcts:
                ctl=CT_TYPES.get(c.get("contact_type",""),"❓")
                csl=c.get("status","not_contacted").replace("_"," ").title()
                with st.expander(f"{ctl} **{c['name']}** — {c.get('title','')} | {csl}"):
                    cc1,cc2=st.columns([3,1])
                    with cc1:
                        if c.get("linkedin_url"): st.markdown(f"🔗 [LinkedIn]({c['linkedin_url']})")
                        if c.get("message_draft"):
                            st.markdown("**Draft:**"); st.code(c["message_draft"])
                        st.text_input("Notes",value=c.get("notes",""),key=f"cn_{j['id']}_{c['id']}")
                    with cc2:
                        ncs=st.selectbox("Status",CT_STAT,index=CT_STAT.index(c.get("status","not_contacted")),key=f"cs_{j['id']}_{c['id']}")
                        if st.button("💾",key=f"csv_{j['id']}_{c['id']}"):
                            c["status"]=ncs
                            if ncs=="request_sent" and not c.get("date_contacted"): c["date_contacted"]=datetime.date.today().isoformat()
                            save_contacts(contacts); st.rerun()
            with st.expander("➕ Add Contact"):
                with st.form(f"ac_{j['id']}"):
                    ac1,ac2=st.columns(2)
                    with ac1: ac_n=st.text_input("Name",key=f"an_{j['id']}"); ac_t=st.text_input("Title",key=f"at_{j['id']}")
                    with ac2: ac_l=st.text_input("LinkedIn",key=f"al_{j['id']}"); ac_y=st.selectbox("Type",list(CT_TYPES.keys()),format_func=lambda x:CT_TYPES[x],key=f"ay_{j['id']}")
                    ac_m=st.text_area("Draft message (max 300 chars)",max_chars=300,height=60,key=f"am_{j['id']}")
                    if st.form_submit_button("Add"):
                        if ac_n:
                            contacts.append({"id":nid(contacts),"job_id":j["id"],"name":ac_n,"title":ac_t,
                                "company":j["company"],"linkedin_url":ac_l,"contact_type":ac_y,
                                "message_draft":ac_m,"status":"not_contacted","date_contacted":None,"response":None,"notes":""})
                            save_contacts(contacts); st.rerun()

        # RESUME
        with rt:
            slug=j.get("company","").lower().replace(" ","-").replace(".","")
            tver=f"tailored_{slug}"
            tp=RESUME_DIR/f"{tver}.json"
            base=load_resume("base")
            if tp.exists():
                st.markdown("✅ Editing tailored version")
                cur=load_resume(tver)
            else:
                st.markdown("Editing from **base resume**. Save creates tailored version.")
                cur=dict(base)

            st.markdown("#### Header")
            hr1,hr2=st.columns(2)
            with hr1: cur["name"]=st.text_input("Name",value=cur.get("name",""),key=f"rn_{j['id']}")
            with hr2: cur["email"]=st.text_input("Email",value=cur.get("email",""),key=f"re_{j['id']}")
            hr3,hr4=st.columns(2)
            with hr3: cur["phone"]=st.text_input("Phone",value=cur.get("phone",""),key=f"rp_{j['id']}")
            with hr4: cur["linkedin"]=st.text_input("LinkedIn",value=cur.get("linkedin",""),key=f"rl_{j['id']}")

            st.markdown("#### Summary")
            cur["summary"]=st.text_area("Summary",value=cur.get("summary",""),height=70,key=f"rsu_{j['id']}")

            st.markdown("#### Competencies")
            cur["competencies"]=[c.strip() for c in st.text_area("One per line",value="\n".join(cur.get("competencies",[])),height=80,key=f"rcm_{j['id']}").split("\n") if c.strip()]

            st.markdown("#### Education")
            for i,edu in enumerate(cur.get("education",[])):
                with st.expander(f"🎓 {edu.get('degree','?')} — {edu.get('school','?')}"):
                    edu["degree"]=st.text_input("Degree",value=edu.get("degree",""),key=f"ed_{j['id']}_{i}")
                    edu["school"]=st.text_input("School",value=edu.get("school",""),key=f"es_{j['id']}_{i}")
                    edu["year"]=st.text_input("Year",value=edu.get("year",""),key=f"ey_{j['id']}_{i}")
                    edu["details"]=st.text_area("Details",value=edu.get("details",""),height=60,key=f"edt_{j['id']}_{i}")

            st.markdown("#### Experience")
            for i,exp in enumerate(cur.get("experience",[])):
                with st.expander(f"💼 {exp.get('role','?')} — {exp.get('company','?')}"):
                    exp["company"]=st.text_input("Company",value=exp.get("company",""),key=f"exc_{j['id']}_{i}")
                    exp["role"]=st.text_input("Role",value=exp.get("role",""),key=f"exr_{j['id']}_{i}")
                    exp["period"]=st.text_input("Period",value=exp.get("period",""),key=f"exp_{j['id']}_{i}")
                    exp["bullets"]=[b.strip() for b in st.text_area("Bullets (one per line)",value="\n".join(exp.get("bullets",[])),height=120,key=f"exb_{j['id']}_{i}").split("\n") if b.strip()]

            st.markdown("#### Leadership")
            for i,ld in enumerate(cur.get("leadership",[])):
                with st.expander(f"🏆 {ld.get('role','?')} — {ld.get('company','?')}"):
                    ld["company"]=st.text_input("Company",value=ld.get("company",""),key=f"ldc_{j['id']}_{i}")
                    ld["role"]=st.text_input("Role",value=ld.get("role",""),key=f"ldr_{j['id']}_{i}")
                    ld["period"]=st.text_input("Period",value=ld.get("period",""),key=f"ldp_{j['id']}_{i}")
                    ld["bullets"]=[b.strip() for b in st.text_area("Bullets",value="\n".join(ld.get("bullets",[])),height=80,key=f"ldb_{j['id']}_{i}").split("\n") if b.strip()]

            st.markdown("#### Projects")
            for i,pr in enumerate(cur.get("projects",[])):
                with st.expander(f"🔬 {pr.get('title',f'Project {i+1}')}"):
                    pr["title"]=st.text_input("Title",value=pr.get("title",""),key=f"prt_{j['id']}_{i}")
                    pr["badge"]=st.text_input("Badge",value=pr.get("badge",""),key=f"prb_{j['id']}_{i}")
                    pr["description"]=st.text_area("Description",value=pr.get("description",""),height=50,key=f"prd_{j['id']}_{i}")
                    pr["tech"]=st.text_input("Tech",value=pr.get("tech",""),key=f"prtc_{j['id']}_{i}")

            st.markdown("#### Publications")
            cur["publications"]=[p.strip() for p in st.text_area("One per paragraph",value="\n\n".join(cur.get("publications",[])),height=100,key=f"rpb_{j['id']}").split("\n\n") if p.strip()]

            st.markdown("#### Conferences")
            cur["conferences"]=[c.strip() for c in st.text_area("One per line",value="\n".join(cur.get("conferences",[])),height=80,key=f"rcf_{j['id']}").split("\n") if c.strip()]

            st.markdown("#### Skills")
            for cat,val in list(cur.get("skills",{}).items()):
                cur["skills"][cat]=st.text_input(cat,value=val,key=f"rsk_{j['id']}_{cat}")

            st.markdown("#### Honors")
            cur["honors"]=[h.strip() for h in st.text_area("One per line",value="\n".join(cur.get("honors",[])),height=60,key=f"rhn_{j['id']}").split("\n") if h.strip()]

            st.markdown("---")
            if st.button("💾 Save Tailored Resume",key=f"rsv_{j['id']}",type="primary"):
                save_resume(cur,tver); j["tailored_resume"]=tver; save_jobs(jobs)
                st.success(f"✅ Saved tailored resume for {j['company']}!")

            if st.button("📄 Generate PDF",key=f"rgen_{j['id']}"):
                title_slug=j.get("title","").lower().replace(" ","-").replace("/","-")[:40]
                pdf_name=f"cv-{slug}-{title_slug}-2026.pdf"
                pdf_out=CAREER_OPS_DIR/"output"/pdf_name
                tmp_html=f"/tmp/cv-tailored-{slug}.html"
                html_content=_build_resume_html(cur, j.get("company",""))
                with open(tmp_html,"w") as f: f.write(html_content)
                try:
                    result=subprocess.run(["node",str(CAREER_OPS_DIR/"generate-pdf.mjs"),tmp_html,str(pdf_out),"--format=letter"],capture_output=True,text=True,timeout=30,cwd=str(CAREER_OPS_DIR))
                    if result.returncode==0:
                        j["pdf_path"]=f"output/{pdf_name}"; save_jobs(jobs)
                        st.success(f"✅ PDF generated: {pdf_name}")
                        st.rerun()
                    else: st.error(f"PDF failed: {result.stderr[:300]}")
                except Exception as e: st.error(f"Error: {e}")

            if j.get("pdf_path"):
                pdf_path = CAREER_OPS_DIR / j["pdf_path"]
                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button("📎 Download PDF", pdf_bytes, pdf_path.name, "application/pdf", key=f"dlrb_{j['id']}")

        # NOTES
        with nt:
            nn=st.text_area("Notes for Varun",value=j.get("notes",""),height=150,key=f"jn_{j['id']}")
            if st.button("💾 Save Notes",key=f"jsv_{j['id']}"):
                j["notes"]=nn; save_jobs(jobs); st.success("Saved!")

        # Delete
        st.markdown("---")
        if st.button(f"🗑️ Delete this job ({j['company']})", key=f"del_{j['id']}"):
            jobs = [x for x in jobs if x["id"]!=j["id"]]
            save_jobs(jobs); st.success(f"Deleted {j['company']}"); st.rerun()

# ================================================================
# RESUME BUILDER
# ================================================================
with tab_resume:
    resume = load_resume("base")
    resume_mode = st.radio("Mode", ["✏️ Edit Base Resume", "🎯 Tailor for Job", "📄 Download PDF"], horizontal=True, key="rm")

    if resume_mode == "✏️ Edit Base Resume":
        st.markdown("## 📝 Base Resume Editor")
        st.caption("Master resume — used as default for all tailoring.")
        st.markdown("### Header")
        h1,h2=st.columns(2)
        with h1: resume["name"]=st.text_input("Name",value=resume.get("name",""),key="bn")
        with h2: resume["email"]=st.text_input("Email",value=resume.get("email",""),key="be")
        h3,h4=st.columns(2)
        with h3: resume["phone"]=st.text_input("Phone",value=resume.get("phone",""),key="bp")
        with h4: resume["linkedin"]=st.text_input("LinkedIn",value=resume.get("linkedin",""),key="bl")
        st.markdown("### Summary")
        resume["summary"]=st.text_area("Professional Summary",value=resume.get("summary",""),height=80,key="bs")
        st.markdown("### Competencies")
        resume["competencies"]=[c.strip() for c in st.text_area("One per line",value="\n".join(resume.get("competencies",[])),height=80,key="bc").split("\n") if c.strip()]
        st.markdown("### Education")
        for i,edu in enumerate(resume.get("education",[])):
            with st.expander(f"🎓 {edu.get('degree','?')} — {edu.get('school','?')}"):
                edu["degree"]=st.text_input("Degree",value=edu.get("degree",""),key=f"bed_{i}")
                edu["school"]=st.text_input("School",value=edu.get("school",""),key=f"bes_{i}")
                edu["year"]=st.text_input("Year",value=edu.get("year",""),key=f"bey_{i}")
                edu["details"]=st.text_area("Details",value=edu.get("details",""),height=60,key=f"bedt_{i}")
        st.markdown("### Work Experience")
        for i,exp in enumerate(resume.get("experience",[])):
            with st.expander(f"💼 {exp.get('role','?')} — {exp.get('company','?')} ({exp.get('period','')})"):
                exp["company"]=st.text_input("Company",value=exp.get("company",""),key=f"bexc_{i}")
                exp["role"]=st.text_input("Role",value=exp.get("role",""),key=f"bexr_{i}")
                exp["period"]=st.text_input("Period",value=exp.get("period",""),key=f"bexp_{i}")
                exp["bullets"]=[b.strip() for b in st.text_area("Bullets (one per line)",value="\n".join(exp.get("bullets",[])),height=150,key=f"bexb_{i}").split("\n") if b.strip()]
        st.markdown("### Leadership & Teaching")
        for i,ld in enumerate(resume.get("leadership",[])):
            with st.expander(f"🏆 {ld.get('role','?')} — {ld.get('company','?')} ({ld.get('period','')})"):
                ld["company"]=st.text_input("Company",value=ld.get("company",""),key=f"bldc_{i}")
                ld["role"]=st.text_input("Role",value=ld.get("role",""),key=f"bldr_{i}")
                ld["period"]=st.text_input("Period",value=ld.get("period",""),key=f"bldp_{i}")
                ld["bullets"]=[b.strip() for b in st.text_area("Bullets",value="\n".join(ld.get("bullets",[])),height=80,key=f"bldb_{i}").split("\n") if b.strip()]
        st.markdown("### Publications")
        resume["publications"]=[p.strip() for p in st.text_area("One per paragraph",value="\n\n".join(resume.get("publications",[])),height=120,key="bpb").split("\n\n") if p.strip()]
        st.markdown("### Conferences")
        resume["conferences"]=[c.strip() for c in st.text_area("One per line",value="\n".join(resume.get("conferences",[])),height=100,key="bcf").split("\n") if c.strip()]
        st.markdown("### Skills")
        for cat,val in list(resume.get("skills",{}).items()):
            resume["skills"][cat]=st.text_input(cat,value=val,key=f"bsk_{cat}")
        st.markdown("### Honors")
        resume["honors"]=[h.strip() for h in st.text_area("One per line",value="\n".join(resume.get("honors",[])),height=60,key="bhn").split("\n") if h.strip()]
        st.markdown("---")
        if st.button("💾 Save Base Resume",type="primary",key="bsv"):
            save_resume(resume,"base"); st.success("✅ Saved!")

    elif resume_mode == "🎯 Tailor for Job":
        st.markdown("## 🎯 Tailor Resume for a Job")
        jl=load_jobs()
        if not jl: st.info("No jobs yet.")
        else:
            opts={f"{j['id']}: {j['company']} — {j['title']}":j for j in jl}
            sel=st.selectbox("Select Job",list(opts.keys()),key="tjsel")
            sj=opts[sel]
            slug=sj.get("company","").lower().replace(" ","-").replace(".","")
            tver=f"tailored_{slug}"
            tp=RESUME_DIR/f"{tver}.json"
            cur=load_resume(tver) if tp.exists() else dict(load_resume("base"))
            if tp.exists(): st.markdown("✅ Editing tailored version")
            else: st.markdown("Editing from base")
            st.markdown(f"**Target:** {sj['title']} at {sj['company']}")
            if sj.get("url"): st.markdown(f"🔗 [View JD]({sj['url']})")
            st.markdown("---")
            st.markdown("### Summary")
            ts=st.text_area("Summary",value=cur.get("summary",""),height=70,key="ts")
            st.markdown("### Competencies")
            tc=st.text_area("One per line",value="\n".join(cur.get("competencies",[])),height=80,key="tc")
            st.markdown("### Experience")
            texps=[]
            for i,exp in enumerate(cur.get("experience",[])):
                with st.expander(f"{exp.get('role','?')} — {exp.get('company','?')}"):
                    txb=st.text_area("Bullets",value="\n".join(exp.get("bullets",[])),height=120,key=f"texb_{i}")
                    texps.append({"company":exp.get("company",""),"role":exp.get("role",""),"period":exp.get("period",""),"bullets":[b.strip() for b in txb.split("\n") if b.strip()]})
            if st.button("💾 Save Tailored",type="primary",key="tsv"):
                t=cur.copy(); t["summary"]=ts; t["competencies"]=[c.strip() for c in tc.split("\n") if c.strip()]; t["experience"]=texps
                save_resume(t,tver)
                ja=load_jobs()
                for jj in ja:
                    if jj["id"]==sj["id"]: jj["tailored_resume"]=tver
                save_jobs(ja); st.success(f"✅ Saved for {sj['company']}!")

    elif resume_mode == "📄 Download PDF":
        st.markdown("## 📄 PDFs")
        vers=["base"]+[f.replace(".json","") for f in os.listdir(RESUME_DIR) if f.startswith("tailored_") and f.endswith(".json")]
        sv=st.selectbox("Version",vers,key="pvs")
        ch=load_resume(sv)
        if ch: st.markdown(f"**Summary:** {ch.get('summary','')[:150]}...")
        pdf_dir=CAREER_OPS_DIR/"output"
        if pdf_dir.exists():
            pdfs=sorted(pdf_dir.glob("*.pdf"),key=os.path.getmtime,reverse=True)
            if pdfs:
                for p in pdfs[:10]:
                    sz=os.path.getsize(p)/1024
                    mt=datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
                    st.markdown(f"📎 [{p.name}]({p}) ({sz:.0f}KB, {mt})")
            else: st.info("No PDFs yet.")
