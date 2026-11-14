from __future__ import annotations

import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository
from simuru_research.ui.tabs import render_selected_page, render_sidebar_navigation

settings = Settings.from_env()
repository = SQLiteRepository(settings.database_path)
auth_qa_service = LocalAuthQAService(
    settings.database_path,
    email_domain="teguhharits.com",
)

st.set_page_config(
    page_title="Simuru Research",
    page_icon=":material/science:",
    layout="wide",
)

st.html(
    """
    <style>
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        footer {
            display: none;
        }
        .stApp {
            background: #f5f6fa;
    }
    .st-key-app-sidebar-expanded,
    .st-key-app-sidebar-collapsed {
        position: fixed;
        z-index: 1000;
        inset: 0 auto 0 0;
        height: 100dvh;
        box-sizing: border-box;
        overflow-x: hidden;
        overflow-y: auto;
        overscroll-behavior: contain;
        border: 0;
        border-right: 1px solid #e2e8f0;
        border-radius: 0;
        background: #ffffff;
        padding: 0.75rem;
        transition: width 180ms ease, box-shadow 180ms ease;
    }
    .st-key-app-sidebar-collapsed {
        width: 4.5rem;
        overflow-y: hidden;
        padding: 0.75rem 0.35rem;
    }
    .st-key-app-sidebar-collapsed:hover,
    .st-key-app-sidebar-collapsed:focus-within {
        width: 17.5rem;
        overflow-y: auto;
        box-shadow: 0 0.5rem 1.5rem #33415526;
    }
    .st-key-app-sidebar-collapsed p {
        font-size: 0;
        line-height: 0;
    }
    .st-key-app-sidebar-collapsed:hover p,
    .st-key-app-sidebar-collapsed:focus-within p {
        font-size: inherit;
        line-height: inherit;
    }
    .st-key-app-sidebar-collapsed .stButton button {
        min-height: 2.8rem;
        justify-content: center;
        overflow: hidden;
        white-space: nowrap;
    }
    .st-key-app-sidebar-collapsed:hover .stButton button,
    .st-key-app-sidebar-collapsed:focus-within .stButton button {
        justify-content: flex-start;
    }
    .st-key-app-sidebar-expanded {
        width: 17.5rem;
    }
    .st-key-app-sidebar-expanded .stButton button,
    .st-key-app-sidebar-collapsed .stButton button {
        border-color: transparent;
        border-radius: 0.65rem;
    }
    .st-key-app-sidebar-expanded .stButton button:hover,
    .st-key-app-sidebar-collapsed .stButton button:hover {
        border-color: #e2e8f0;
    }
    .st-key-app-sidebar-brand p {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        white-space: nowrap;
    }
    .st-key-app-sidebar-brand span {
        font-size: 1.5rem;
        line-height: 1;
    }
    .st-key-app-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        width: auto !important;
        box-sizing: border-box;
        z-index: 900;
        margin-bottom: 1rem;
        border: 1px solid #e8eaf1;
        border-radius: 0 0 0.75rem 0.75rem;
        background: #ffffffee;
        box-shadow: 0 0.15rem 0.5rem #33415512;
        padding: 0.7rem 2rem 0.7rem 20rem;
        backdrop-filter: blur(12px);
    }
    body:has(.st-key-app-sidebar-collapsed:not(:hover):not(:focus-within))
    .st-key-app-topbar {
        padding-left: 6rem;
    }
    .st-key-overview-hero {
        min-height: 12rem;
        border: 0;
        border-radius: 0.85rem;
        background: linear-gradient(115deg, #ffffff 0%, #f0efff 100%);
        box-shadow: 0 0.25rem 1rem #33415512;
        padding: 1.5rem;
    }
    .st-key-overview-hero h3 {
        color: #696cff;
    }
    .st-key-overview-latest-card,
    .st-key-overview-active-emails-card,
    .st-key-overview-run-summary {
        min-height: 12rem;
        border-color: #eceef4;
        border-radius: 0.85rem;
        background: #ffffff;
        box-shadow: 0 0.25rem 1rem #33415512;
    }
    .st-key-overview-activity-chart,
    .st-key-overview-run-summary {
        border-color: #eceef4;
        border-radius: 0.85rem;
        border: 1px solid #e2e8f0;
        background: #ffffff;
        box-shadow: 0 0.25rem 1rem #33415512;
    }
    .st-key-app-breadcrumbs {
        min-height: 2rem;
        align-items: center;
        color: #64748b;
        margin-bottom: 0.75rem;
    }
    .st-key-app-breadcrumbs .stButton button {
        min-height: 2rem;
        border: 0;
        background: transparent;
        color: #64748b;
        padding: 0 0.25rem;
    }
    .st-key-app-breadcrumbs .stButton button:hover {
        color: #696cff;
    }
    .st-key-app-page-card {
        border: 1px solid #e6e9f0;
        border-radius: 1rem;
        background: #ffffff;
        box-shadow: 0 0.25rem 1rem #33415512, 0 0.05rem 0.15rem #33415508;
        padding: 1.25rem;
    }
    .st-key-domain-email-list .stButton button {
        overflow: hidden;
    }
    .st-key-domain-email-list .stButton button p {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    @media (max-width: 1024px) {
        .st-key-app-sidebar-expanded,
        .st-key-app-sidebar-collapsed {
            width: 4.5rem;
            overflow-y: hidden;
            padding: 0.75rem 0.35rem;
        }
        .st-key-app-sidebar-expanded:hover,
        .st-key-app-sidebar-expanded:focus-within,
        .st-key-app-sidebar-collapsed:hover,
        .st-key-app-sidebar-collapsed:focus-within {
            width: min(17.5rem, calc(100vw - 3.5rem));
            overflow-y: auto;
            box-shadow: 0 0.5rem 1.5rem #33415526;
        }
        .st-key-app-sidebar-expanded p,
        .st-key-app-sidebar-collapsed p {
            font-size: 0;
            line-height: 0;
        }
        .st-key-app-sidebar-expanded:hover p,
        .st-key-app-sidebar-expanded:focus-within p,
        .st-key-app-sidebar-collapsed:hover p,
        .st-key-app-sidebar-collapsed:focus-within p {
            font-size: inherit;
            line-height: inherit;
        }
        .st-key-app-sidebar-expanded .stButton button,
        .st-key-app-sidebar-collapsed .stButton button {
            min-height: 2.8rem;
            justify-content: center;
            overflow: hidden;
            white-space: nowrap;
        }
        .st-key-app-sidebar-expanded:hover .stButton button,
        .st-key-app-sidebar-expanded:focus-within .stButton button,
        .st-key-app-sidebar-collapsed:hover .stButton button,
        .st-key-app-sidebar-collapsed:focus-within .stButton button {
            justify-content: flex-start;
        }
        .st-key-app-sidebar-brand p {
            justify-content: center;
        }
        .st-key-app-sidebar-expanded:hover .st-key-app-sidebar-brand p,
        .st-key-app-sidebar-expanded:focus-within .st-key-app-sidebar-brand p,
        .st-key-app-sidebar-collapsed:hover .st-key-app-sidebar-brand p,
        .st-key-app-sidebar-collapsed:focus-within .st-key-app-sidebar-brand p {
            justify-content: flex-start;
        }
        .st-key-app-topbar {
            padding-left: 5.5rem;
            padding-right: 1rem;
        }
        .st-key-app-page-card {
            border-radius: 0.85rem;
            padding: 1rem;
        }
    }
    @media (max-width: 640px) {
        .st-key-app-topbar {
            padding: 0.6rem 0.75rem 0.6rem 4.75rem;
        }
        .st-key-app-topbar p {
            margin-bottom: 0;
        }
        .st-key-app-page-card {
            border-radius: 0.75rem;
            padding: 0.75rem;
        }
        .st-key-app-breadcrumbs {
            margin-bottom: 0.5rem;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .st-key-app-sidebar-expanded,
        .st-key-app-sidebar-collapsed {
            transition: none;
        }
    }
    </style>
    """
)

st.session_state.setdefault("app_sidebar_collapsed", False)
sidebar_collapsed = st.session_state.get("app_sidebar_collapsed", False)
sidebar_column, content_column = st.columns(
    [0.2, 9.8] if sidebar_collapsed else [1.55, 8.45],
    gap="small",
)
with sidebar_column:
    sidebar_key = (
        "app-sidebar-collapsed" if sidebar_collapsed else "app-sidebar-expanded"
    )
    with st.container(key=sidebar_key):
        with st.container(key="app-sidebar-brand"):
            st.markdown(":material/science: **Simuru Research**")
        if st.button(
            "Expand sidebar" if sidebar_collapsed else "Collapse sidebar",
            icon=(
                ":material/chevron_right:"
                if sidebar_collapsed
                else ":material/chevron_left:"
            ),
            help="Expand sidebar" if sidebar_collapsed else "Collapse sidebar",
            key="toggle_app_sidebar",
            width="stretch",
        ):
            st.session_state["app_sidebar_collapsed"] = not sidebar_collapsed
            st.rerun()
        render_sidebar_navigation()

with content_column:
    current_page = st.session_state.get("current_page", "Overview")
    page_labels = {
        "Overview": "Dashboard",
        "Mailbox": "List email",
        "Sandbox Batch": "Sandbox batch",
        "Registration QA": "Registration QA",
        "Run History & Export": "Run history & export",
        "SIMURU API": "SIMURU API",
    }
    with st.container(key="app-topbar"):
        st.markdown(f"**{page_labels.get(current_page, 'Dashboard')}**")
        st.caption("Simuru Research  /  Research workspace")
    st.space(96)
    render_selected_page(
        settings=settings,
        repository=repository,
        auth_qa_service=auth_qa_service,
    )
