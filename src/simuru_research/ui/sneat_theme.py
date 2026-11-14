from __future__ import annotations

import streamlit as st


def inject_sneat_css() -> None:
    """Apply a Sneat-inspired layout while retaining native Streamlit components."""
    st.markdown(
        """
        <style>
        :root {
          --sneat-primary: #696cff;
          --sneat-primary-soft: #e7e7ff;
          --sneat-text: #566a7f;
          --sneat-muted: #a1acb8;
          --sneat-bg: #f5f5f9;
          --sneat-border: #e7e7ff;
          --sneat-shadow: 0 2px 6px rgba(67, 89, 113, .12);
        }
        .stApp { background: var(--sneat-bg); color: var(--sneat-text); }
        [data-testid="stHeader"] { background: rgba(245,245,249,.92); }
        [data-testid="stSidebar"] {
          background: #fff; border-right: 1px solid var(--sneat-border);
        }
        [data-testid="stSidebar"] > div:first-child { padding: 1.1rem .8rem; }
        [data-testid="stSidebar"] [data-testid="stButton"] button {
          border: 0; border-radius: .55rem; background: transparent;
          color: var(--sneat-text); text-align: left; justify-content: flex-start;
          min-height: 2.65rem; padding: .5rem .75rem;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button:hover {
          background: var(--sneat-primary-soft); color: var(--sneat-primary);
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
          background: var(--sneat-primary-soft); color: var(--sneat-primary);
          font-weight: 650;
        }
        .sneat-topbar {
          background:#fff; border:1px solid var(--sneat-border);
          box-shadow:var(--sneat-shadow); border-radius:.6rem;
          padding:.9rem 1.2rem; margin:0 0 1.25rem 0;
          display:flex; align-items:center; justify-content:space-between;
        }
        .sneat-brand { font-size:1.45rem; font-weight:750; color:#435971; letter-spacing:-.04em; }
        .sneat-brand span { color:var(--sneat-primary); }
        .sneat-page-title { font-size:1.45rem; font-weight:650; color:#435971; margin:.15rem 0 .25rem; }
        .sneat-breadcrumb { color:var(--sneat-muted); font-size:.83rem; margin-bottom:1.1rem; }
        .sneat-card {
          background:#fff; border:1px solid var(--sneat-border);
          border-radius:.65rem; box-shadow:var(--sneat-shadow);
          padding:1.1rem 1.2rem; margin-bottom:1rem;
        }
        .sneat-kpi-label { color:#8592a3; font-size:.85rem; font-weight:550; }
        .sneat-kpi-value { color:#435971; font-size:1.65rem; font-weight:700; margin-top:.2rem; }
        .sneat-kpi-foot { color:#71dd37; font-size:.78rem; margin-top:.15rem; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
          border-radius:.65rem; border-color:var(--sneat-border);
          box-shadow:var(--sneat-shadow); background:#fff;
        }
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
          background:var(--sneat-primary); border-color:var(--sneat-primary);
          color:#fff; border-radius:.5rem; font-weight:600;
          box-shadow:0 2px 4px rgba(105,108,255,.35);
        }
        .stButton > button, .stDownloadButton > button {
          border-radius:.5rem; min-height:2.5rem;
        }
        input, textarea, [data-baseweb="select"] > div {
          border-radius:.45rem !important;
        }
        [data-testid="stDataFrame"] { border:1px solid var(--sneat-border); border-radius:.55rem; }
        [data-testid="stAlert"] { border-radius:.55rem; }
        h1,h2,h3 { color:#435971; letter-spacing:-.025em; }
        @media (max-width: 768px) {
          .sneat-topbar { padding:.7rem .85rem; }
          .sneat-page-title { font-size:1.2rem; }
          .sneat-card { padding:.85rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar() -> None:
    st.markdown(
        """
        <div class="sneat-topbar">
          <div class="sneat-brand"><span>✦</span> simuru</div>
          <div style="color:#8592a3;font-size:.9rem">Research workspace&nbsp;&nbsp; · &nbsp;&nbsp;Local QA</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_heading(title: str, section: str) -> None:
    st.markdown(
        f'<div class="sneat-breadcrumb">Home&nbsp; / &nbsp;{section}</div>'
        f'<div class="sneat-page-title">{title}</div>',
        unsafe_allow_html=True,
    )


def render_kpi(label: str, value: str, foot: str = "") -> None:
    st.markdown(
        '<div class="sneat-card">'
        f'<div class="sneat-kpi-label">{label}</div>'
        f'<div class="sneat-kpi-value">{value}</div>'
        f'<div class="sneat-kpi-foot">{foot or "&nbsp;"}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
