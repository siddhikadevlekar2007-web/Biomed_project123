"""PharmaGuard: educational medication interaction information assistant."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import auth
import database
from faiss_engine import DrugInteractionSearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="PharmaGuard", page_icon="🩺", layout="wide")

# ---------- PharmaGuard pastel UI ----------
st.markdown("""
<style>
:root {
    --ink: #344054;
    --muted: #667085;
    --lavender: #EDE9FE;
    --mint: #DDF5EC;
    --blue: #E3F0FF;
    --peach: #FFF0E5;
    --pink: #FCE7F3;
}
.stApp {
    background: linear-gradient(135deg, #FAF8FF 0%, #F3FAFF 48%, #F2FBF7 100%);
    color: var(--ink);
}
.block-container { max-width: 1450px; padding-top: 1.5rem; }
h1, h2, h3 { color: #51477A !important; }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #EDE9FE 0%, #E3F0FF 55%, #DDF5EC 100%);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #51477A !important; }
div[data-testid="stMetric"] {
    background: rgba(255,255,255,.82);
    border: 1px solid #E5E0F5;
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 6px 20px rgba(92, 82, 145, .07);
    transition: transform .2s ease, box-shadow .2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 24px rgba(92, 82, 145, .12);
}
.stButton > button, .stFormSubmitButton > button {
    background: linear-gradient(120deg, #A99BEA, #8FCBB9);
    color: #fff !important; border: 0; border-radius: 12px;
    font-weight: 650; transition: .2s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    filter: brightness(.97); transform: translateY(-2px);
    box-shadow: 0 7px 16px rgba(126, 113, 184, .2);
}
input, textarea { border-radius: 10px !important; }
div[data-testid="stAlert"] { border-radius: 14px; }
div[data-testid="stPlotlyChart"] {
    background: rgba(255,255,255,.8); border: 1px solid #E9E4F5;
    border-radius: 18px; padding: 8px;
}
div[data-testid="stDataFrame"] {
    border: 1px solid #E5E0F5; border-radius: 14px; overflow: hidden;
}
hr { border-color: #E5E0F5 !important; }
@keyframes pgFade {
    from {opacity:0; transform:translateY(8px);}
    to {opacity:1; transform:translateY(0);}
}
.block-container { animation: pgFade .45s ease-out; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

def pastel_banner(title, subtitle, emoji="🩺"):
    st.markdown(f"""
    <div style="background:linear-gradient(120deg,#EDE9FE,#E3F0FF,#DDF5EC);
                border:1px solid #E4DFF4;border-radius:22px;padding:24px 28px;
                margin-bottom:18px;">
      <div style="font-size:34px;font-weight:800;color:#51477A;">{emoji} {title}</div>
      <div style="font-size:15px;color:#667085;margin-top:7px;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown(
    """
    <div style="background:#fff3cd;border:2px solid #d39e00;border-radius:8px;
            st.caption("Pastel medical dashboard")
        st.divider()
        st.subheader("Sign in")
        with st.form("login_form"):
            role = st.selectbox("I am a", ("User", "Admin"))
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            if auth.authenticate(username, password, role):
                st.success(f"Signed in as {role}.")
                st.rerun()
            st.error("Sign-in failed. Check your role, username, and password.")
        st.caption("Demo accounts: User `user` / `user123`; Admin `admin` / `admin123`.")
    return bool(st.session_state.get("authenticated"))


def _render_interaction_result(row: dict[str, Any]) -> None:
    severity_colors = {
        "Low": "#2e8b57",
        "Moderate": "#d4a017",
        "High": "#e87500",
        "Critical": "#c62828",
    }
    severity = row["severity"]
    st.markdown(
        f"### {row['drug1']} + {row['drug2']} "
        f"<span style='color:{severity_colors.get(severity, '#555')};font-size:0.8em'>"
        f"— {severity} risk</span>",
        unsafe_allow_html=True,
    )
    gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=int(row["percentile"]),
            number={"suffix": "%"},
            title={"text": "Knowledge-base risk percentile*"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": severity_colors.get(severity, "#496a81")},
                "steps": [
                    {"range": [0, 25], "color": "#e8f5e9"},
                    {"range": [25, 50], "color": "#fff8e1"},
                    {"range": [50, 75], "color": "#fff3e0"},
                    {"range": [75, 100], "color": "#ffebee"},
                ],
            },
        )
    )
    gauge.update_layout(height=230, margin={"t": 55, "b": 10, "l": 25, "r": 25})
    left, right = st.columns([1, 2])
    with left:
        st.plotly_chart(gauge, use_container_width=True, key=f"gauge_{row['id']}")
        st.caption("*Editorial indicator only; not an individual probability or validated clinical score.")
    with right:
        st.markdown(f"**How the medicines interact**  \n{row['mechanism']}")
        st.markdown(f"**What may be happening in the body**  \n{row['what_happens']}")
        st.markdown(f"**Why this may be harmful**  \n{row['why_harmful']}")
        st.markdown(f"**Symptoms to watch for**  \n{row['symptoms']}")
        st.info(f"**Precautions and next steps:** {row['precautions']}")
    st.divider()


def _render_checker(records: list[dict[str, Any]]) -> None:
    pastel_banner(
        "Medication Interaction Checker",
        "Choose medicines to explore documented interaction pairs.",
        "💊"
    )
    st.write("Select medications you currently take or are considering discussing with a clinician.")
    medications = sorted(
        {str(row[field]).strip() for row in records for field in ("drug1", "drug2")},
        with first:
            drug1 = st.text_input("Medication 1")
            severity = st.selectbox("Severity", database.SEVERITIES)
            mechanism = st.text_area("Pharmacological mechanism")
            why_harmful = st.text_area("Why it may be harmful")
            precautions = st.text_area("Precautions / mitigation")
        with second:
            drug2 = st.text_input("Medication 2")
            percentile = st.number_input("Editorial risk percentile", min_value=0, max_value=100, value=50)
            what_happens = st.text_area("What happens biologically")
            symptoms = st.text_area("Symptoms to watch for")
        submitted = st.form_submit_button("Save interaction and rebuild search index")
    if submitted:
        try:
            database.add_interaction(
                {
                    "drug1": drug1,
                    "drug2": drug2,
                    "severity": severity,
                    "percentile": percentile,
                    "mechanism": mechanism,
                    "what_happens": what_happens,
                    "why_harmful": why_harmful,
                    "symptoms": symptoms,
                    "precautions": precautions,
                }
            )
            refreshed = database.get_interactions()
            st.session_state["faiss_engine"] = DrugInteractionSearch(refreshed)
            st.session_state["faiss_signature"] = tuple(
                (row.get("id"), row["drug1"].casefold(), row["drug2"].casefold())
                for row in refreshed
            )
            st.success("Interaction saved; the search index has been rebuilt.")
            st.rerun()
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
    st.subheader("Current knowledge base")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Medication 1": row["drug1"],
                    "Medication 2": row["drug2"],
                    "Severity": row["severity"],
                    "Risk percentile*": row["percentile"],
                }
                for row in records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("*Editorial indicator only; not an individualized probability.")


try:
    database.initialize_database()
    database.initialize_session_state()
except RuntimeError as exc:
    logger.exception("Database initialization failed")
    st.error(str(exc))
    st.stop()

if not _render_login():
    st.info("Sign in to access PharmaGuard.")
    st.stop()

with st.sidebar:
    st.write(f"Signed in: **{st.session_state['username']}** ({st.session_state['role']})")
    if st.button("Log out", use_container_width=True):
        auth.logout()
        st.rerun()
    pages = ["Interaction checker", "Analytics"]
    if st.session_state["role"] == "Admin":
        pages.append("Admin dashboard")
    page = st.radio("Navigate", pages)

try:
    interaction_records = database.get_interactions()
except RuntimeError as exc:
    logger.exception("Could not load interactions")
    st.error(str(exc))
    st.stop()

if page == "Interaction checker":
    _render_checker(interaction_records)
elif page == "Analytics":
    _render_analytics(interaction_records)
elif page == "Admin dashboard" and st.session_state["role"] == "Admin":
    _render_admin(interaction_records)

# ---------- Footer ----------
st.markdown("""
<div style="margin-top:28px;padding:18px;text-align:center;
            background:linear-gradient(120deg,#EDE9FE,#E3F0FF,#DDF5EC);
            border:1px solid #E5E0F5;border-radius:16px;">
  <div style="font-weight:800;color:#51477A;">🩺 PharmaGuard</div>
  <div style="font-size:12px;color:#667085;margin-top:4px;">
    Educational information only • Consult a qualified clinician or pharmacist
  </div>
</div>
""", unsafe_allow_html=True)

    
                padding:14px 18px;color:#4a3900;font-weight:600;margin-bottom:16px">
