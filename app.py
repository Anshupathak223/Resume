"""Dashboard-style Streamlit UI for the resume screener. Run: streamlit run app.py"""
import os
import re
import tempfile
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import screener

USER_NAME = "Rishi"  # shown in the greeting and sidebar

st.set_page_config(page_title="Resume Screener", page_icon="", layout="wide")

P_DASH, P_SCREEN, P_CAND, P_ANALYTICS = (
    "  Dashboard", " New Screening", "  Candidates", "  Analytics"
)
CATS = {  # key: (display name, max points)
    "required_skills": ("Required skills", 40),
    "experience": ("Experience", 25),
    "education": ("Education", 15),
    "preferred_skills": ("Preferred skills", 10),
    "certifications": ("Certifications", 10),
}
DECISIONS = ["Undecided", "Shortlist", "Hold", "Reject"]
STATUS = {
    "Undecided": ("To review", "amber"), "Shortlist": ("Shortlisted", "green"),
    "Hold": ("On hold", "slate"), "Reject": ("Rejected", "red"),
}
BANDS = [(80, "Strong Match", "green"), (65, "Good Match", "blue"),
         (50, "Potential Match", "amber"), (0, "Low Match", "red")]
DONUT_COLORS = ["#16A34A", "#2563EB", "#F59E0B", "#EF4444"]


LIGHT = dict(page="#F5F7FC", card="#FFFFFF", line="#E6EAF5", rowline="#EEF1F8", thbg="#F5F7FC",
             head="#0F1B4D", ink="#0F172A", body="#1E293B", muted="#64748B",
             track="rgba(15,23,42,.1)", icbg="rgba(255,255,255,.8)", side1="#0B1437", side2="#111C4E",
             tip="linear-gradient(135deg,#EEF2FF,#E0E7FF)",
             t_blue="blue", t_violet="violet", t_green="green", t_orange="orange",
             g_bg="#DCFCE7", g_fg="#15803D", b_bg="#DBEAFE", b_fg="#1D4ED8", a_bg="#FEF3C7", a_fg="#B45309",
             r_bg="#FEE2E2", r_fg="#B91C1C", s_bg="#E2E8F0", s_fg="#475569", i_bg="#E0E7FF", i_fg="#3730A3")
DARK_T = dict(page="#0E1117", card="#161B2E", line="#263050", rowline="#232B45", thbg="#1C2238",
              head="#E6EAFF", ink="#F1F5F9", body="#CBD5E1", muted="#94A3B8",
              track="rgba(255,255,255,.12)", icbg="rgba(255,255,255,.08)", side1="#070B1E", side2="#0D1438",
              tip="linear-gradient(135deg,rgba(99,102,241,.25),rgba(79,70,229,.15))",
              t_blue="rgba(59,130,246,.14)", t_violet="rgba(139,92,246,.14)",
              t_green="rgba(16,185,129,.14)", t_orange="rgba(245,158,11,.14)",
              g_bg="rgba(34,197,94,.18)", g_fg="#4ADE80", b_bg="rgba(59,130,246,.2)", b_fg="#93C5FD",
              a_bg="rgba(245,158,11,.2)", a_fg="#FCD34D", r_bg="rgba(239,68,68,.2)", r_fg="#FCA5A5",
              s_bg="rgba(148,163,184,.2)", s_fg="#CBD5E1", i_bg="rgba(99,102,241,.25)", i_fg="#C7D2FE")


def is_dark():
    """Follow Streamlit's active theme (system setting or the one picked in the app menu)."""
    try:
        t = st.context.theme.type
        if t in ("light", "dark"):
            return t == "dark"
    except Exception:
        pass
    return st.get_option("theme.base") == "dark"


DARK = is_dark()
T = DARK_T if DARK else LIGHT
st.markdown("<style>:root{" + "".join(f"--{k.replace('_', '-')}:{v};" for k, v in T.items()) + "}</style>",
            unsafe_allow_html=True)

st.markdown("""<style>
footer{visibility:hidden}
header[data-testid="stHeader"]{background:transparent}
.stApp{background:var(--page)}
.block-container{padding-top:1.6rem;max-width:1300px}
h1,h2,h3{color:var(--head)}
[data-testid="stBaseButton-primary"]{background:#4F46E5;border-color:#4F46E5;color:#fff}
[data-testid="stBaseButton-primary"]:hover{background:#4338CA;border-color:#4338CA}
.stProgress>div>div>div>div{background:#4F46E5}
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--side1),var(--side2))}
[data-testid="stSidebar"] div[role="radiogroup"] label{padding:.65rem .9rem;border-radius:10px;width:100%;margin-bottom:2px;cursor:pointer}
[data-testid="stSidebar"] div[role="radiogroup"] label>div:first-child{display:none}
[data-testid="stSidebar"] div[role="radiogroup"] label p{color:#C7D2FE;font-weight:500;font-size:.95rem}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:#3142C9}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p{color:#fff}
.brand{display:flex;gap:.6rem;align-items:center;color:#fff;font-weight:700;font-size:1.15rem;padding:.2rem .3rem 1.2rem}
.usercard{display:flex;gap:.7rem;align-items:center;margin-top:2rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,.12);color:#fff;font-size:.9rem}
.usercard small{color:#A5B4FC;display:block}
.sidehint{color:#8791C9;font-size:.75rem;margin-top:1.2rem;line-height:1.4}
.card{background:var(--card);border:1px solid var(--line);color:var(--body);border-radius:16px;padding:1.2rem 1.3rem;box-shadow:0 1px 3px rgba(15,27,77,.05);margin-bottom:1rem}
.card h4{margin:0 0 .9rem;color:var(--head);font-size:1.05rem}
.kpi{border-radius:16px;padding:1.1rem 1.2rem;display:flex;gap:1rem;align-items:center;border:1px solid var(--line)}
.kpi .ic{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.3rem;background:var(--icbg);flex:none}
.kpi .lb{font-size:.72rem;letter-spacing:.06em;color:var(--muted);font-weight:600}
.kpi .v{font-size:1.9rem;font-weight:800;color:var(--ink);line-height:1.1}
.kpi .sb{font-size:.78rem;color:var(--muted)}
.kpi .bar{height:6px;background:var(--track);border-radius:99px;margin-top:.4rem;overflow:hidden;width:160px;max-width:100%}
.kpi .bar i{display:block;height:100%;border-radius:99px}
.t-blue{background:var(--t-blue)}.t-violet{background:var(--t-violet)}.t-green{background:var(--t-green)}.t-orange{background:var(--t-orange)}
.pill{display:inline-block;padding:.15rem .6rem;border-radius:8px;font-size:.78rem;font-weight:600}
.chip{display:inline-block;padding:.12rem .6rem;border-radius:99px;font-size:.78rem;font-weight:500;margin:0 .3rem .3rem 0}
.green{background:var(--g-bg);color:var(--g-fg)}.blue{background:var(--b-bg);color:var(--b-fg)}
.amber{background:var(--a-bg);color:var(--a-fg)}.red{background:var(--r-bg);color:var(--r-fg)}
.slate{background:var(--s-bg);color:var(--s-fg)}.indigo{background:var(--i-bg);color:var(--i-fg)}
.avatar{width:36px;height:36px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:.8rem;flex:none}
.who{display:flex;gap:.7rem;align-items:center}
table.rt{width:100%;border-collapse:collapse;font-size:.88rem}
table.rt th{text-align:left;background:var(--thbg);color:var(--muted);font-weight:600;padding:.6rem .7rem;font-size:.78rem}
table.rt td{padding:.6rem .7rem;border-bottom:1px solid var(--rowline);color:var(--body)}
.donutwrap{display:flex;gap:1.4rem;align-items:center}
.donut{width:150px;height:150px;border-radius:50%;position:relative;flex:none}
.hole{position:absolute;inset:22px;background:var(--card);border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center}
.hole b{font-size:1.6rem;color:var(--ink)}.hole span{font-size:.72rem;color:var(--muted)}
.leg{display:flex;justify-content:space-between;gap:1.2rem;font-size:.85rem;color:var(--body);margin:.3rem 0}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:.5rem}
.tip{background:var(--tip);border-radius:16px;padding:1.2rem 1.3rem;color:var(--body)}
.tip b{display:block;color:var(--head);font-size:1.05rem;margin:.3rem 0}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px}
</style>""", unsafe_allow_html=True)


AVATARS_LIGHT = [("#E0E7FF", "#3730A3"), ("#DCFCE7", "#166534"), ("#FCE7F3", "#9D174D"),
                 ("#FEF3C7", "#92400E"), ("#DBEAFE", "#1E40AF")]
AVATARS_DARK = [("rgba(99,102,241,.3)", "#C7D2FE"), ("rgba(34,197,94,.25)", "#86EFAC"),
                ("rgba(236,72,153,.25)", "#F9A8D4"), ("rgba(245,158,11,.25)", "#FCD34D"),
                ("rgba(59,130,246,.25)", "#93C5FD")]

# ------------------------------------------------------------- helpers -----
def H(s):  # collapse HTML so markdown never treats indentation as code
    return "".join(line.strip() for line in s.splitlines())


def name_of(f):
    stem = re.sub(r"^\d+[_\-\s]*", "", Path(f).stem).replace("_", " ").replace("-", " ").strip()
    return stem.title() or Path(f).stem


def avatar(f):
    n = name_of(f).split()
    pal = AVATARS_DARK if DARK else AVATARS_LIGHT
    bg, fg = pal[sum(map(ord, f)) % len(pal)]
    return f"<span class='avatar' style='background:{bg};color:{fg}'>{escape(''.join(p[0] for p in n[:2]).upper() or '?')}</span>"


def band(total):
    return next((lbl, col) for floor, lbl, col in BANDS if total >= floor)


def chips(items, color):
    return "".join(f"<span class='chip {color}'>{escape(s)}</span>" for s in items) or "<span style='color:#94A3B8'>None</span>"


def decision(f):
    return st.session_state["decisions"].get(f, "Undecided")


def goto(page):
    st.session_state["_goto"] = page


def kpi(icon, label, value, sub, tint, pct=None, bar="#4F46E5"):
    b = f"<div class='bar'><i style='width:{pct}%;background:{bar}'></i></div>" if pct is not None else ""
    return H(f"<div class='kpi t-{tint}'><div class='ic'>{icon}</div><div>"
             f"<div class='lb'>{label}</div><div class='v'>{value}</div><div class='sb'>{sub}</div>{b}</div></div>")


def export_rows(rows):
    out = []
    for r in rows:
        d = r["detail"]
        out.append({
            "file": r["file"], "total": r["total"], "label": r["label"],
            **{k: r[k] for k in CATS}, "decision": decision(r["file"]),
            "notes": st.session_state["notes"].get(r["file"], ""), "summary": d.summary,
            "matched_required": "; ".join(d.matched_required_skills),
            "missing_required": "; ".join(d.missing_required_skills),
            "strengths": "; ".join(d.strengths), "gaps": "; ".join(d.gaps),
            "reasoning": d.reasoning, "recommendation": d.recommendation,
        })
    return pd.DataFrame(out).to_csv(index=False).encode("utf-8-sig")


# --------------------------------------------------------------- state -----
for k, v in {"results": [], "decisions": {}, "notes": {}, "jd": "", "nav": P_DASH}.items():
    st.session_state.setdefault(k, v)
if "_goto" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_goto")

results = st.session_state["results"]
ok = [r for r in results if "detail" in r]

with st.sidebar:
    st.markdown("<div class='brand'> Resume Screener</div>", unsafe_allow_html=True)
    page = st.radio("Navigation", [P_DASH, P_SCREEN, P_CAND, P_ANALYTICS],
                    key="nav", label_visibility="collapsed")
    st.markdown(H(f"<div class='usercard'><span class='avatar' style='background:#C7D2FE;color:#312E81'>"
                  f"{escape(USER_NAME[:2].upper())}</span><div>{escape(USER_NAME)}<small>Recruiter</small></div></div>"),
                unsafe_allow_html=True)
    st.markdown("<div class='sidehint'>Switch light or dark mode from the ⋮ menu (top right) → Settings → Theme.</div>",
                unsafe_allow_html=True)


def empty_state():
    st.markdown(H("<div class='card' style='text-align:center;padding:2.5rem'><div style='font-size:2rem'>📄</div>"
                  "<h4>No candidates screened yet</h4><div style='color:#64748B'>Add a job description and "
                  "resumes to get match scores and summaries.</div></div>"), unsafe_allow_html=True)
    st.button("Start a screening", type="primary", on_click=goto, args=(P_SCREEN,))


# ----------------------------------------------------------- dashboard -----
def page_dashboard():
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    c1, c2 = st.columns([4, 1])
    c1.title(f"{greet}, {USER_NAME} 👋")
    c1.caption("Candidate screening that helps you find the best matches faster.")
    c2.button("＋  New Screening", type="primary", on_click=goto, args=(P_SCREEN,))
    if not ok:
        return empty_state()

    decs = st.session_state["decisions"]
    n, short = len(results), sum(v == "Shortlist" for v in decs.values())
    strong = sum(r["label"] == "Strong Match" for r in ok)
    k = st.columns(4)
    k[0].markdown(kpi("👥", "TOTAL CANDIDATES", n, "uploaded this session", "blue"), unsafe_allow_html=True)
    k[1].markdown(kpi("📄", "SCREENED", len(ok), f"{round(100 * len(ok) / n)}% completed", "violet",
                      round(100 * len(ok) / n), "#4F46E5"), unsafe_allow_html=True)
    k[2].markdown(kpi("⭐", "SHORTLISTED", short, f"{round(100 * short / n)}% of candidates", "green",
                      round(100 * short / n), "#10B981"), unsafe_allow_html=True)
    k[3].markdown(kpi("🏆", "STRONG MATCHES", strong, "score 80 or above", "orange"), unsafe_allow_html=True)

    left, right = st.columns([2.2, 1])
    with left:
        m = re.search(r"Job Title:\s*(.+)", st.session_state["jd"])
        title = m.group(1).strip() if m else "Active job"
        freq = Counter(s for r in ok for s in r["detail"].matched_required_skills + r["detail"].missing_required_skills)
        skills = [s for s, _ in freq.most_common(6)]
        st.markdown(H(f"<div class='card'><h4>Active Job</h4><div class='who'><span class='avatar indigo' "
                      f"style='border-radius:10px;width:46px;height:46px'>&lt;/&gt;</span><div><b style='font-size:1.1rem'>"
                      f"{escape(title)}</b><div style='color:#64748B;font-size:.85rem'>{n} candidates · {len(ok)} screened"
                      f"</div></div></div><div style='margin-top:.9rem'>{chips(skills, 'indigo')}</div></div>"),
                    unsafe_allow_html=True)

        rows = ""
        for r in sorted(ok, key=lambda r: r["total"], reverse=True)[:5]:
            d = r["detail"]
            mt = len(d.matched_required_skills)
            tot = mt + len(d.missing_required_skills)
            sl, sc = STATUS[decision(r["file"])]
            rows += (f"<tr><td><div class='who'>{avatar(r['file'])}<b>{escape(name_of(r['file']))}</b></div></td>"
                     f"<td><span class='pill {band(r['total'])[1]}'>{r['total']}</span></td><td>{mt}/{tot}</td>"
                     f"<td>{r['experience']}/25</td><td><span class='pill {sc}'>{sl}</span></td></tr>")
        st.markdown(H("<div class='card'><h4>Recent Candidates</h4><table class='rt'><tr><th>Candidate</th>"
                      "<th>Match score</th><th>Required skills</th><th>Experience pts</th><th>Status</th></tr>"
                      f"{rows}</table></div>"), unsafe_allow_html=True)
        st.button("View all candidates →", on_click=goto, args=(P_CAND,))

    with right:
        counts = [sum(band(r["total"])[0] == b[1] for r in ok) for b in BANDS]
        grad, acc = [], 0
        for c, col in zip(counts, DONUT_COLORS):
            grad.append(f"{col} {acc / len(ok) * 100:.1f}% {(acc + c) / len(ok) * 100:.1f}%")
            acc += c
        avg = round(sum(r["total"] for r in ok) / len(ok))
        rng = ["80–100", "65–79", "50–64", "0–49"]
        leg = "".join(f"<div class='leg'><span><i class='dot' style='background:{DONUT_COLORS[i]}'></i>{rng[i]}</span>"
                      f"<b>{counts[i]}</b></div>" for i in range(4))
        st.markdown(H(f"<div class='card'><h4>Match Score Distribution</h4><div class='donutwrap'>"
                      f"<div class='donut' style='background:conic-gradient({', '.join(grad)})'><div class='hole'>"
                      f"<b>{avg}</b><span>Avg. score</span></div></div><div style='flex:1'>{leg}</div></div></div>"),
                    unsafe_allow_html=True)
        st.markdown("<div class='tip'>✨<b>Smarter hiring, better teams</b>Scores are recommendations. "
                    "You make every final decision.</div>", unsafe_allow_html=True)


# ----------------------------------------------------------- screening -----
def page_screening():
    st.title("New Screening")
    st.caption("Paste the job description, upload resumes, and review each candidate's match.")
    default = st.session_state["jd"] or (Path("jd.txt").read_text(encoding="utf-8") if Path("jd.txt").exists() else "")
    jd = st.text_area("Job description", value=default, height=260)
    files = st.file_uploader("Resumes (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    redact = st.toggle("Redact emails, phone numbers and URLs before sending to the model", value=True)
    if not st.button("Screen candidates", type="primary"):
        return
    if not os.getenv("GEMINI_API_KEY"):
        return st.error("GEMINI_API_KEY not found. Check your .env file.")
    if not jd.strip() or not files:
        return st.warning("Add a job description and at least one resume.")

    client = screener.get_client()
    out = []
    with st.status("Screening candidates...", expanded=True) as status:
        bar = st.progress(0.0)
        for i, f in enumerate(files, 1):
            st.write(f"Reading and scoring **{f.name}** ({i}/{len(files)})")
            row = {"file": f.name, "error": ""}
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / Path(f.name).name
                    path.write_bytes(f.getvalue())
                    text = screener.extract_text(path)
                if len(text) < 100:
                    raise ValueError("Little or no text extracted (scanned PDF?)")
                ev = screener.evaluate(client, jd, screener.redact_pii(text) if redact else text)
                row.update(screener.compute_result(ev))
                row["detail"] = ev
            except Exception as e:
                row["error"] = str(e)
            out.append(row)
            bar.progress(i / len(files))
        status.update(label="Screening complete", state="complete")
    st.session_state.update(results=out, decisions={}, notes={}, jd=jd, _goto=P_DASH)
    st.rerun()


# ---------------------------------------------------------- candidates -----
def page_candidates():
    st.title("Candidates")
    if not ok:
        return empty_state()
    for r in results:
        if "detail" not in r:
            st.warning(f"{r['file']}: {r['error']}")

    f1, f2, f3, f4 = st.columns([2, 1.5, 2, 1.5])
    q = f1.text_input("Search", placeholder="Name or skill, e.g. Docker").lower()
    min_score = f2.slider("Minimum score", 0, 100, 0)
    levels = f3.multiselect("Match level", [b[1] for b in BANDS], default=[b[1] for b in BANDS])
    sort_by = f4.selectbox("Sort by", ["Total score"] + [v[0] for v in CATS.values()])
    key = "total" if sort_by == "Total score" else next(k for k, v in CATS.items() if v[0] == sort_by)

    def passes(r):
        d = r["detail"]
        pool = [name_of(r["file"])] + d.matched_required_skills + d.matched_preferred_skills
        return r["total"] >= min_score and r["label"] in levels and (not q or any(q in s.lower() for s in pool))

    shown = sorted((r for r in ok if passes(r)), key=lambda r: r[key], reverse=True)
    t1, t2, t3 = st.tabs([f"Candidates ({len(shown)})", "Compare", "Export"])

    with t1:
        for rank, r in enumerate(shown, 1):
            ev, f = r["detail"], r["file"]
            col = band(r["total"])[1]
            with st.container(border=True):
                st.markdown(H(f"<div class='who' style='justify-content:space-between'><div class='who'>{avatar(f)}"
                              f"<div><b style='font-size:1.05rem'>#{rank} {escape(name_of(f))}</b>"
                              f"<div style='color:#94A3B8;font-size:.78rem'>{escape(f)}</div></div></div>"
                              f"<div><span class='pill {col}'>{r['label']}</span> "
                              f"<span class='pill {col}' style='font-size:1rem'>{r['total']}/100</span></div></div>"),
                            unsafe_allow_html=True)
                st.markdown(f"**Candidate summary**  \n{ev.summary}")
                st.markdown(chips(ev.matched_required_skills, "green") + chips(ev.missing_required_skills, "red"),
                            unsafe_allow_html=True)
                with st.expander("Score breakdown and reasoning"):
                    for c, (k_, (lbl, mx)) in zip(st.columns(5), CATS.items()):
                        c.caption(f"{lbl}: {r[k_]}/{mx}")
                        c.progress(r[k_] / mx)
                    a, b = st.columns(2)
                    a.markdown("**Matched preferred**")
                    a.markdown(chips(ev.matched_preferred_skills, "green"), unsafe_allow_html=True)
                    b.markdown("**Missing preferred**")
                    b.markdown(chips(ev.missing_preferred_skills, "slate"), unsafe_allow_html=True)
                    a.markdown("**Strengths**\n" + "\n".join(f"- {s}" for s in ev.strengths))
                    b.markdown("**Gaps**\n" + "\n".join(f"- {g}" for g in ev.gaps))
                    st.markdown("**Reasoning**")
                    st.write(ev.reasoning)
                    st.markdown("**Recommendation for human review**")
                    st.write(ev.recommendation)
                d1, d2 = st.columns([2, 3])
                st.session_state["decisions"][f] = d1.radio(
                    "Your decision", DECISIONS, horizontal=True, key=f"dec_{f}",
                    index=DECISIONS.index(decision(f)))
                st.session_state["notes"][f] = d2.text_input(
                    "Notes", key=f"note_{f}", value=st.session_state["notes"].get(f, ""),
                    placeholder="Your notes for this candidate")

    with t2:
        pick = st.multiselect("Choose 2 to 4 candidates", [r["file"] for r in ok], max_selections=4,
                              format_func=name_of)
        if len(pick) >= 2:
            sel = [r for r in ok if r["file"] in pick]
            table = {}
            for r in sel:
                col_ = {"Total": f"{r['total']}/100", "Level": r["label"]}
                col_.update({v[0]: f"{r[k_]}/{v[1]}" for k_, v in CATS.items()})
                col_["Missing required"] = ", ".join(r["detail"].missing_required_skills) or "None"
                table[name_of(r["file"])] = col_
            st.table(pd.DataFrame(table))
            for r in sel:
                st.markdown(f"**{name_of(r['file'])}**: {r['detail'].summary}")
        else:
            st.info("Pick at least two candidates to compare them side by side.")

    with t3:
        sl = [r for r in ok if decision(r["file"]) == "Shortlist"]
        st.download_button("Download all results (CSV)", export_rows(ok), "results.csv", "text/csv")
        st.download_button(f"Download shortlisted ({len(sl)})", export_rows(sl), "shortlist.csv",
                           "text/csv", disabled=not sl)


# ----------------------------------------------------------- analytics -----
def page_analytics():
    st.title("Analytics")
    if not ok:
        return empty_state()
    a, b = st.columns(2)
    with a:
        st.markdown("<div class='card'><h4>Average score by category</h4></div>", unsafe_allow_html=True)
        for k_, (lbl, mx) in CATS.items():
            avg = sum(r[k_] for r in ok) / len(ok)
            st.caption(f"{lbl}: {avg:.1f}/{mx}")
            st.progress(avg / mx)
    with b:
        st.markdown("<div class='card'><h4>Most commonly missing required skills</h4></div>", unsafe_allow_html=True)
        miss = Counter(s for r in ok for s in r["detail"].missing_required_skills)
        if miss:
            st.bar_chart(pd.DataFrame(miss.most_common(10), columns=["Skill", "Candidates missing it"]).set_index("Skill"))
        else:
            st.success("No required skills are missing across candidates.")
    st.markdown("<div class='card'><h4>Score composition by candidate</h4></div>", unsafe_allow_html=True)
    df = pd.DataFrame([{"Candidate": name_of(r["file"]), **{v[0]: r[k_] for k_, v in CATS.items()}} for r in ok])
    st.bar_chart(df, x="Candidate", y=[v[0] for v in CATS.values()])


{P_DASH: page_dashboard, P_SCREEN: page_screening, P_CAND: page_candidates, P_ANALYTICS: page_analytics}[page]()
