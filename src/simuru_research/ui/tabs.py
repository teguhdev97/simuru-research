from __future__ import annotations

import streamlit as st

from simuru_research.ui.api_tab import render_api_tab
from simuru_research.ui.history_tab import render_history_tab
from simuru_research.ui.mailbox_tab import create_cpanel_manager, render_mailbox_tab
from simuru_research.ui.overview_tab import render_overview_tab
from simuru_research.ui.registration_qa_tab import render_registration_qa_tab
from simuru_research.ui.sandbox_tab import render_sandbox_tab
from simuru_research.ui.website_registration_tab import render_website_registration_tab

APP_PAGES = {
    "Sandbox Batch": ("Sandbox batch", ":material/science:"),
    "Registration QA": ("Registration QA", ":material/verified_user:"),
    "Website Registration": ("Website Registration", ":material/language:"),
    "Run History & Export": ("Run history & export", ":material/history:"),
    "SIMURU API": ("SIMURU API", ":material/api:"),
}


def _navigate(page: str) -> None:
    st.session_state["current_page"] = page


def _page_button(page: str, label: str, icon: str) -> None:
    st.button(
        label,
        key=f"navigate_{page.lower().replace(' ', '_')}",
        icon=icon,
        type=(
            "primary"
            if st.session_state.get("current_page", "Overview") == page
            else "secondary"
        ),
        width="stretch",
        on_click=_navigate,
        args=(page,),
    )


def render_sidebar_navigation() -> None:
    st.caption("DASHBOARDS")
    _page_button("Overview", "Overview", ":material/dashboard:")

    st.caption("APPS & PAGES")
    _page_button("Mailbox", "List email", ":material/mail:")

    for page, (label, icon) in APP_PAGES.items():
        _page_button(page, label, icon)


def render_selected_page(
    settings,
    repository,
    auth_qa_service,
) -> None:
    selected_page = st.session_state.get("current_page", "Overview")
    page_labels = {
        "Overview": "Dashboard",
        "Mailbox": "List email",
        "Sandbox Batch": "Sandbox batch",
        "Registration QA": "Registration QA",
        "Website Registration": "Website Registration",
        "Run History & Export": "Run history & export",
        "SIMURU API": "SIMURU API",
    }
    if selected_page not in page_labels:
        selected_page = "Overview"
        st.session_state["current_page"] = selected_page
    page_label = page_labels[selected_page]

    with st.container(
        key="app-breadcrumbs",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
        wrap=False,
    ):
        if selected_page != "Overview":
            st.button(
                "Dashboard",
                icon=":material/dashboard:",
                key="breadcrumb_overview",
                on_click=_navigate,
                args=("Overview",),
                width="content",
            )
            st.caption("›")
        st.markdown(f"**{page_label}**")

    with st.container(key="app-page-card"):
        if selected_page == "Overview":
            render_overview_tab(repository)
        elif selected_page == "Mailbox":
            render_mailbox_tab(settings, create_cpanel_manager())
        elif selected_page == "Sandbox Batch":
            render_sandbox_tab(
                repository,
                min(settings.default_total_jobs, 100),
                min(settings.default_max_workers, 10),
            )
        elif selected_page == "Registration QA":
            render_registration_qa_tab(
                repository,
                auth_qa_service,
                create_cpanel_manager(),
            )
        elif selected_page == "Website Registration":
            render_website_registration_tab(
                settings.database_path,
                auth_qa_service,
            )
        elif selected_page == "Run History & Export":
            render_history_tab(repository)
        elif selected_page == "SIMURU API":
            render_api_tab(settings)


def render_all_tabs(
    settings,
    repository,
    auth_qa_service,
) -> None:
    render_sidebar_navigation()
    render_selected_page(
        settings=settings,
        repository=repository,
        auth_qa_service=auth_qa_service,
    )
