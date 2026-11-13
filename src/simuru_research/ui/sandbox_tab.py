from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.engine.runner import BatchRunner


def render_sandbox_tab(repository, total_jobs: int, max_workers: int) -> None:
    st.subheader("Run synthetic QA batch")
    st.write(
        "Batch lokal untuk menguji antrean, concurrency, penyimpanan SQLite, "
        "dan ekspor hasil. Data sintetis ini tidak membuat akun eksternal."
    )
    if st.button("Run sandbox batch", type="primary", use_container_width=True):
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
            st.dataframe(
                pd.DataFrame(results),
                use_container_width=True,
                hide_index=True,
            )