import streamlit as st
import copy, json, os, datetime
from pathlib import Path

from generate_resume_pdf import generate_pdf
from resume_renderer import (
    build_resume_html,
    load_resume as load_resume_file,
    normalize_resume_version,
    resume_paths,
    resume_version_for_job,
    save_resume as save_resume_file,
)

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

def load_resume(version="base"):
    return load_resume_file(version)

def save_resume(data, version="base"):
    save_resume_file(data, version)

load_jobs = lambda: lj(DATA_DIR / "jobs.json", [])
save_jobs = lambda d: sj(DATA_DIR / "jobs.json", d)
load_contacts = lambda: lj(DATA_DIR / "contacts.json", [])
save_contacts = lambda d: sj(DATA_DIR / "contacts.json", d)
def nid(items): return max((i.get("id",0) for i in items), default=0) + 1

STATUS = ["discovered","evaluated","interested","applying","applied","interviewing","offer","rejected","withdrawn"]
S_EMOJI = {"discovered":"⚪","evaluated":"🟡","interested":"🟠","applying":"🔵","applied":"🔷","interviewing":"🟢","offer":"🎉","rejected":"🔴","withdrawn":"⚫"}
CT_STAT = ["not_contacted","search_placeholder","request_sent","responded","call_scheduled","met"]
CT_TYPES = {"hiring_manager":"👔 Hiring Mgr","team_lead":"🧪 Team Lead","recruiter":"🔍 Recruiter","peer":"🤝 Peer","ceo":"🏢 CEO","search_placeholder":"🔎 Search Target"}

def option_index(options, value, default=0):
    try:
        return options.index(value)
    except ValueError:
        return default

def parse_iso_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None

def linked_resume_version(job):
    return normalize_resume_version(job.get("tailored_resume")) or resume_version_for_job(job)

st.markdown("""<style>
.apply-btn{display:inline-block;background:#2563EB;color:#fff!important;padding:6px 16px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px}
.apply-btn:hover{background:#1D4ED8}
</style>""", unsafe_allow_html=True)

# --- Resume HTML builder ---
def _build_resume_html(resume, company=""):
    return build_resume_html(resume, CAREER_OPS_DIR / "templates" / "cv-template.html")

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
        ev = [j for j in jobs if isinstance(j.get("score"), (int, float))]
        avg = sum(j["score"] for j in ev)/len(ev) if ev else 0
        high_score = len([j for j in jobs if isinstance(j.get("score"), (int, float)) and j["score"] >= 4.0])
        today_iso = datetime.date.today().isoformat()
        new_jobs = len([j for j in jobs if j.get("date_found") == today_iso])
        not_applied = len([j for j in jobs if j.get("status") not in ("applied", "interviewing", "offer", "rejected")])
        od = [
            j for j in jobs
            if parse_iso_date(j.get("follow_up_date"))
            and parse_iso_date(j.get("follow_up_date")).isoformat() <= today_iso
            and j.get("status") in ("applied","interviewing")
        ]
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
            follow_date = parse_iso_date(j.get("follow_up_date")) or datetime.date.today()
            d=(datetime.date.today()-follow_date).days
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
            cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
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
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        rows = []
        for j in filtered_jobs:
            applied = j.get("applied_date") if j.get("applied_date") else ""
            followup = j.get("follow_up_date") if j.get("follow_up_date") else ""
            has_pdf = "📄" if j.get("pdf_path") and (CAREER_OPS_DIR / j["pdf_path"]).exists() else ""
            # Add NEW badge for today's jobs
            is_new = "🆕 " if j.get("date_found") == today else ""
            score_val = j.get("score")
            rows.append({
                "ID": j["id"],
                "Company": is_new + j.get("company",""),
                "Role": j.get("title","")[:50],
                "Score": "—" if score_val is None else f"{score_val:.1f}",
                "Status": j.get("status","discovered"),
                "Location": j.get("location",""),
                "Found": j.get("date_found",""),
                "Applied": applied,
                "Follow": followup,
                "PDF": has_pdf
            })
        df = pd.DataFrame(rows)

        # Use st.dataframe with row selection
        selection = st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "ID": st.column_config.NumberColumn("ID"),
                "Score": st.column_config.Column("Score"),
                "PDF": st.column_config.Column("PDF")
            },
            key="job_table"
        )
        
        # Get selected job from row click
        j = None
        if selection.selection.rows:
            selected_idx = selection.selection.rows[0]
            selected_id = int(df.iloc[selected_idx]["ID"])
            st.session_state["selected_job_id"] = selected_id
            j = next((x for x in jobs if x["id"]==selected_id), None)
        elif st.session_state.get("selected_job_id"):
            j = next((x for x in jobs if x["id"]==st.session_state["selected_job_id"]), None)
        
        # Edit section for selected job
        if j:
            with st.expander(f"✏️ Edit {j['company']} - Status & Dates", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_status = st.selectbox("Status", STATUS, index=option_index(STATUS, j.get("status","discovered")), key=f"edit_status_{j['id']}")
                with c2:
                    new_applied = st.text_input("Applied Date", value=j.get("applied_date",""), key=f"edit_applied_{j['id']}")
                with c3:
                    new_follow = st.text_input("Follow-up Date", value=j.get("follow_up_date",""), key=f"edit_follow_{j['id']}")
                if st.button("💾 Save Changes", key=f"save_{j['id']}"):
                    j["status"] = new_status
                    j["applied_date"] = new_applied if new_applied else None
                    j["follow_up_date"] = new_follow if new_follow else None
                    save_jobs(jobs)
                    st.success("Saved!")
        else:
            st.info("👆 Click any row to view and edit job details")

        # Export CSV
        csv_df = pd.DataFrame([{
            "Company": j.get("company",""),
            "Title": j.get("title",""),
            "Score": "—" if j.get("score") is None else f"{j.get('score'):.1f}",
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
        sc_str = f"⭐{j['score']:.1f}" if isinstance(j.get("score"), (int, float)) else ""

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
        
        date_bits = [f"📍 {j.get('location','—')}", f"📅 Found: {j.get('date_found','—')}"]
        if j.get('date_posted'):
            date_bits.append(f"🕒 Posted: {j.get('date_posted')}")
        st.caption(" | ".join(date_bits))
        
        # Edit fields
        st.markdown("#### Update Job")
        ed1, ed2, ed3, ed4 = st.columns([1.5,1.5,1.5,1])
        with ed1:
            ns = st.selectbox("Status", STATUS, index=option_index(STATUS, j.get("status","discovered")), key=f"s_{j['id']}")
        with ed2:
            na = st.date_input("Applied", value=parse_iso_date(j.get("applied_date")), key=f"ja_{j['id']}")
        with ed3:
            nf = st.date_input("Follow-up", value=parse_iso_date(j.get("follow_up_date")) or datetime.date.today()+datetime.timedelta(days=7), key=f"jf_{j['id']}")
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
                if isinstance(ev, dict):
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
                    st.markdown(str(ev))
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
                        contact_notes = st.text_input("Notes",value=c.get("notes",""),key=f"cn_{j['id']}_{c['id']}")
                    with cc2:
                        ncs=st.selectbox("Status",CT_STAT,index=option_index(CT_STAT, c.get("status","not_contacted")),key=f"cs_{j['id']}_{c['id']}")
                        if st.button("💾",key=f"csv_{j['id']}_{c['id']}"):
                            c["status"]=ncs
                            c["notes"]=contact_notes
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
            tver=linked_resume_version(j)
            tp,_=resume_paths(tver)
            base=load_resume("base")
            if tp.exists():
                st.markdown("✅ Editing tailored version")
                cur=load_resume(tver)
            else:
                st.markdown("Editing from **base resume**. Save creates tailored version.")
                cur=copy.deepcopy(base)

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
                save_resume(cur,tver); j["tailored_resume"]=tver
                pdf_path=generate_pdf(tver, j.get("company",""), j.get("title",""))
                if pdf_path:
                    j["pdf_path"]=pdf_path; save_jobs(jobs)
                    st.success(f"✅ PDF generated: {Path(pdf_path).name}")
                    st.rerun()
                else:
                    st.error("PDF generation failed. Check the terminal output for details.")

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
        teaching = dict(resume.get("teaching", {}))
        with st.expander("👨‍🏫 Teaching Experience", expanded=bool(teaching)):
            teaching["role"] = st.text_input("Teaching Role", value=teaching.get("role", ""), key="btr")
            teaching["school"] = st.text_input("Institution", value=teaching.get("school", ""), key="bts")
            teaching["period"] = st.text_input("Teaching Period", value=teaching.get("period", ""), key="btp")
            teaching["description"] = st.text_area("Teaching Description", value=teaching.get("description", ""), height=80, key="btd")
        resume["teaching"] = teaching
        st.markdown("### Projects")
        for i,pr in enumerate(resume.get("projects",[])):
            with st.expander(f"🔬 {pr.get('title', f'Project {i+1}')}"):
                pr["title"]=st.text_input("Title",value=pr.get("title",""),key=f"bprt_{i}")
                pr["badge"]=st.text_input("Badge",value=pr.get("badge",""),key=f"bprb_{i}")
                pr["description"]=st.text_area("Description",value=pr.get("description",""),height=60,key=f"bprd_{i}")
                pr["tech"]=st.text_input("Tech",value=pr.get("tech",""),key=f"bprtech_{i}")
        st.markdown("### Publications")
        resume["publications"]=[p.strip() for p in st.text_area("One per paragraph",value="\n\n".join(resume.get("publications",[])),height=120,key="bpb").split("\n\n") if p.strip()]
        st.markdown("### Conferences")
        resume["conferences"]=[c.strip() for c in st.text_area("One per line",value="\n".join(resume.get("conferences",[])),height=100,key="bcf").split("\n") if c.strip()]
        st.markdown("### Certifications")
        resume["certifications"]=[c.strip() for c in st.text_area("One per line",value="\n".join(resume.get("certifications",[])),height=80,key="bcrt").split("\n") if c.strip()]
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
            tver=linked_resume_version(sj)
            tp,_=resume_paths(tver)
            cur=load_resume(tver) if tp.exists() else copy.deepcopy(load_resume("base"))
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
        pdf_dir=CAREER_OPS_DIR/"data"/"output"
        if pdf_dir.exists():
            pdfs=sorted(pdf_dir.glob("*.pdf"),key=os.path.getmtime,reverse=True)
            if pdfs:
                for p in pdfs[:10]:
                    sz=os.path.getsize(p)/1024
                    mt=datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
                    st.markdown(f"📎 [{p.name}]({p}) ({sz:.0f}KB, {mt})")
            else: st.info("No PDFs yet.")

# --- Archived Jobs Section ---
st.markdown("---")
with st.expander("📦 Archived Jobs (stale/closed or > 6 months old) - Click to view"):
    archived = lj(DATA_DIR / "archived_jobs.json", [])
    if archived:
        st.markdown(f"**{len(archived)} archived jobs**")
        
        # Build dataframe
        import pandas as pd
        rows = []
        for j in archived:
            rows.append({
                "ID": j["id"],
                "Company": j.get("company",""),
                "Role": j.get("title","")[:50],
                "Score": "—" if j.get("score") is None else f"{j.get('score'):.1f}",
                "Date": j.get("date_found",""),
                "Status": j.get("status","discovered")
            })
        df = pd.DataFrame(rows)
        
        st.dataframe(df, width="stretch", hide_index=True)
        
        # Select archived job to view
        opts = {f"{j['id']}: {j['company']} - {j['title'][:40]}": j for j in archived}
        sel = st.selectbox("Select archived job to view:", [""] + list(opts.keys()), key="arch_sel")
        if sel:
            aj = opts[sel]
            archive_reason = aj.get('archive_reason')
            st.markdown(f"### {aj['company']} — {aj['title']}")
            if aj.get('date_posted'):
                st.markdown(f"**Date Posted:** {aj.get('date_posted')}")
            st.markdown(f"**Discovered:** {aj.get('date_found','Unknown')}")
            st.markdown(f"**Original Score:** {aj.get('score','N/A')}")
            if archive_reason:
                st.warning(f"Archived reason: {archive_reason}")
            if aj.get('url'):
                closed_reason = (archive_reason or '').lower()
                label = "🔗 Original listing URL" if any(x in closed_reason for x in ['stale', 'closed', 'not found', 'no longer accepting']) else "🔗 Check if still open"
                st.link_button(label, aj['url'])
            if archive_reason:
                st.markdown("**💡 Tip:** Prefer fresh or directly-posted roles over archived wrappers unless you have a specific outreach reason.")
            else:
                st.markdown("**💡 Tip:** Reach out to the company's talent acquisition team to ask if this role is still active or if similar positions are open.")
    else:
        st.info("No archived jobs yet. Jobs older than 6 months will appear here.")
