from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.storage.exporter import results_to_csv
from simuru_research.ui.pagination import render_paginated_dataframe


def render_history_tab(repository) -> None:
    st.subheader("Local run history")
    all_runs = repository.list_runs(limit=None)
    if not all_runs:
        st.info("Run history masih kosong.")
    else:
        render_paginated_dataframe(
            pd.DataFrame(all_runs),
            key="run_history_pagination",
            alt="Local QA run history",
        )
        run_ids = [item["run_id"] for item in all_runs]
        selected_run = st.selectbox("Select run to export", run_ids)
        selected_results = repository.list_results(selected_run)
        if selected_results:
            csv_export = results_to_csv(selected_results)
            st.download_button(
                "Download selected run as CSV",
                data=csv_export,
                file_name=f"simuru-research-{selected_run[:8]}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            render_paginated_dataframe(
                pd.DataFrame(selected_results),
                key="run_results_pagination",
                alt="Results for the selected run",
            )