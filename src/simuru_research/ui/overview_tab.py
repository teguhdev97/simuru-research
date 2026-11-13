from __future__ import annotations

import pandas as pd
import streamlit as st


def render_overview_tab(repository, team_accounts) -> None:
    runs = repository.list_runs(limit=1)
    counts = team_accounts.count_by_type()
    account_total = sum(counts.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Team accounts", account_total)
    c2.metric("Personal", counts["personal"])
    c3.metric("Creator", counts["creator"])
    c4.metric("Business", counts["business"])

    if runs:
        latest = runs[0]
        st.subheader("Latest QA run")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Run ID", latest["run_id"][:8])
        r2.metric("QA jobs", latest["total_jobs"])
        r3.metric("Passed", latest["passed"])
        r4.metric("Failed", latest["failed"])
        st.caption(f"Latest run started: {latest['started_at']}")
        latest_results = repository.list_results(latest["run_id"])
        if latest_results:
            st.dataframe(
                pd.DataFrame(latest_results),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info(
            "Belum ada sandbox run. Buka tab Sandbox Batch "
            "untuk menjalankan test identities."
        )

    st.subheader("Integration scope")
    st.markdown(
        "- Team Accounts: metadata registry for accounts owned by "
        "or authorized for the team to manage.\n"
        "- Instagram API: available for eligible professional "
        "Creator/Business accounts after OAuth.\n"
        "- Personal Instagram accounts: registry-only; no official "
        "Instagram API connection.\n"
        "- SIMURU: read-only account and catalog research endpoints.\n"
        "- Registration QA: local signup, email/SMS verification, "
        "and login tests only.\n"
        "- No third-party signup, OTP retrieval, or number rental is performed."
    )