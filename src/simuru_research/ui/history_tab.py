from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.storage.exporter import results_to_csv


def render_history_tab(repository) -> None:
    st.subheader("Local run history")
    all_runs = repository.list_runs(limit=50)
    if not all_runs:
        st.info("Run history masih kosong.")
    else:
        st.dataframe(pd.DataFrame(all_runs), use_container_width=True, hide_index=True)
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
            st.dataframe(
                pd.DataFrame(selected_results),
                use_container_width=True,
                hide_index=True,
            )