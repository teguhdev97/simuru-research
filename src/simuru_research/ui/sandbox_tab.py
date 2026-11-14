from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.engine.runner import BatchRunner
from simuru_research.ui.pagination import render_paginated_dataframe


def render_sandbox_tab(repository, total_jobs: int, max_workers: int) -> None:
    st.subheader("Run synthetic QA batch")
    st.write(
        "Batch lokal untuk menguji antrean, concurrency, penyimpanan SQLite, "
        "dan ekspor hasil. Data sintetis ini tidak membuat akun eksternal."
    )

    with st.container(border=True, key="sandbox-run-settings"):
        total_col, workers_col = st.columns(2, vertical_alignment="bottom")
        with total_col:
            total_jobs = st.number_input(
                "Synthetic test identities",
                min_value=1,
                max_value=100,
                value=total_jobs,
                step=1,
                key="sandbox_total_jobs",
            )
        with workers_col:
            max_workers = st.number_input(
                "Concurrent workers",
                min_value=1,
                max_value=10,
                value=max_workers,
                step=1,
                help="Bounded local workers. No browser sessions or external signups.",
                key="sandbox_max_workers",
            )

    if st.button(
        "Run sandbox batch",
        type="primary",
        width="stretch",
        key="run_sandbox_batch",
    ):
        with st.spinner(
            f"Running {total_jobs} synthetic jobs with {max_workers} workers..."
        ):
            summary = BatchRunner(repository).run_batch(
                total_jobs=int(total_jobs),
                max_workers=int(max_workers),
            )
        st.success(
            f"Run {summary.run_id[:8]} selesai: "
            f"{summary.passed} passed · {summary.failed} failed."
        )

    recent = repository.list_runs(limit=1)
    if recent:
        active_run = recent[0]
        results = repository.list_results(active_run["run_id"])
        st.markdown(f"Latest run: {active_run['run_id']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total", active_run["total_jobs"])
        m2.metric("Passed", active_run["passed"])
        m3.metric("Failed", active_run["failed"])
        if results:
            render_paginated_dataframe(
                pd.DataFrame(results),
                key="sandbox_results_pagination",
                alt="Latest sandbox run results",
            )