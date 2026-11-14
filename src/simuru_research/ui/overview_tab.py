from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.ui.pagination import render_paginated_dataframe

RESULTS_PER_PAGE = 6


def render_overview_tab(repository) -> None:
    runs = repository.list_runs(limit=10)
    active_email_count = _active_email_count()

    hero_col, latest_col, emails_col = st.columns(
        [2.4, 1, 1],
        gap="medium",
        vertical_alignment="top",
    )
    with hero_col:
        with st.container(key="overview-hero"):
            st.subheader("Research workspace")
            st.markdown(
                "Ringkasan mailbox domain dan hasil pengujian terbaru."
            )
            st.button(
                "Open email inbox",
                icon=":material/mail:",
                type="primary",
                key="overview_open_mailbox",
                on_click=_open_mailbox,
            )
    with latest_col:
        with st.container(key="overview-latest-card", border=True):
            st.markdown("**Latest QA run**")
            if runs:
                latest = runs[0]
                st.metric("Jobs", int(latest["total_jobs"]))
                st.caption(
                    f"{int(latest['passed'])} passed · {int(latest['failed'])} failed"
                )
            else:
                st.metric("Jobs", "—")
                st.caption("No runs yet")
    with emails_col:
        with st.container(key="overview-active-emails-card", border=True):
            st.markdown("**Active emails**")
            st.metric("Domain mailboxes", active_email_count)
            st.caption("Email addresses available in List email.")
            st.button(
                "Open List email",
                icon=":material/mail:",
                key="overview_open_active_emails",
                on_click=_open_mailbox,
                width="stretch",
            )

    with st.container(key="overview-activity-chart", border=True):
        st.subheader("QA activity")
        if runs:
            activity = pd.DataFrame(
                [
                    {
                        "Run": str(run["run_id"])[:8],
                        "Passed": int(run["passed"]),
                        "Failed": int(run["failed"]),
                    }
                    for run in reversed(runs)
                ]
            ).set_index("Run")
            st.bar_chart(
                activity,
                height=290,
                color=["#696cff", "#ff6b6b"],
                alt="Passed and failed jobs across the latest QA runs",
            )
        else:
            st.info("Belum ada data pengujian untuk ditampilkan.")

    with st.container(key="overview-run-summary", border=True):
        st.subheader("Latest run summary")
        if runs:
            latest = runs[0]
            total_jobs = int(latest["passed"]) + int(latest["failed"])
            if total_jobs:
                pass_rate = int(latest["passed"]) / total_jobs * 100
                st.metric("Latest run pass rate", f"{pass_rate:.0f}%")
            else:
                st.metric("Latest run pass rate", "—")
        else:
            st.caption("Pass rate will appear after the first QA run.")

    if runs:
        latest = runs[0]
        results = repository.list_results(str(latest["run_id"]))
        if results:
            with st.container(border=True):
                st.subheader("Latest run details")
                render_paginated_dataframe(
                    pd.DataFrame(results),
                    key="overview_results_pagination",
                    alt="Results from the latest QA run",
                    page_size=RESULTS_PER_PAGE,
                )


def _active_email_count() -> int:
    addresses = st.session_state.get("domain_email_addresses", [])
    if addresses:
        return len(set(addresses))
    created = {
        row.get("email", "")
        for row in st.session_state.get("latest_mailbox_batch", [])
        if isinstance(row, dict) and row.get("status") == "created"
    }
    return len(created - {""})


def _open_mailbox() -> None:
    st.session_state["current_page"] = "Mailbox"
