from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.engine.runner import BatchRunner
from simuru_research.providers.simuru_client import SimuruAPIError, SimuruClient
from simuru_research.storage.database import SQLiteRepository
from simuru_research.storage.exporter import results_to_csv

settings = Settings.from_env()
repository = SQLiteRepository(settings.database_path)

st.set_page_config(page_title="Simuru Research", page_icon="🧪", layout="wide")
st.title("Simuru Research Lab")
st.caption("Read-only API connectivity · Local sandbox QA · SQLite history")

with st.sidebar:
    st.subheader("Run configuration")
    total_jobs = st.number_input(
        "Synthetic test users", min_value=1, max_value=100,
        value=min(settings.default_total_jobs, 100), step=1
    )
    max_workers = st.number_input(
        "Concurrent workers", min_value=1, max_value=10,
        value=min(settings.default_max_workers, 10), step=1,
        help="Bounded local workers. This does not open browser sessions."
    )
    st.divider()
    st.caption("All generated identities are fictional sandbox data.")
    st.caption("No third-party account registration or OTP retrieval is performed.")

overview_tab, sandbox_tab, history_tab, api_tab = st.tabs(
    ["Overview", "Sandbox Batch", "Run History & Export", "Simuru API"]
)

with overview_tab:
    runs = repository.list_runs(limit=1)
    if runs:
        latest = runs[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Latest run", latest["run_id"][:8])
        c2.metric("Synthetic jobs", latest["total_jobs"])
        c3.metric("Passed", latest["passed"])
        c4.metric("Failed", latest["failed"])
        st.caption(f"Latest run started: {latest['started_at']}")
        latest_results = repository.list_results(latest["run_id"])
        if latest_results:
            st.dataframe(pd.DataFrame(latest_results), use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada sandbox run. Buka tab Sandbox Batch untuk menjalankan test identities.")

    st.subheader("Project boundaries")
    st.markdown(
        "- Simuru integration: read-only profile check only.\n"
        "- Sandbox identities: example.test and fictional 555-0100–0199 phone range.\n"
        "- No email/phone rentals, OTP retrieval, proxy rotation, or third-party signup."
    )

with sandbox_tab:
    st.subheader("Run synthetic QA batch")
    st.write(
        "Jalankan batch lokal untuk menguji antrean, concurrency, penyimpanan SQLite, "
        "dan ekspor hasil. Data yang dibuat bukan akun pada layanan eksternal."
    )
    if st.button("Run sandbox batch", type="primary", use_container_width=True):
        with st.spinner(f"Running {total_jobs} synthetic jobs with {max_workers} workers..."):
            summary = BatchRunner(repository).run_batch(
                total_jobs=int(total_jobs), max_workers=int(max_workers)
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
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

with history_tab:
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
            st.download_button(
                "Download selected run as CSV",
                data=results_to_csv(selected_results),
                file_name=f"simuru-research-{selected_run[:8]}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.dataframe(pd.DataFrame(selected_results), use_container_width=True, hide_index=True)

with api_tab:
    st.subheader("Simuru read-only connection")
    st.write(
        "Pemeriksaan ini hanya memanggil GET /api/profile untuk memvalidasi koneksi "
        "dan API key. Tidak ada pembelian, penyewaan, pemanggilan OTP, atau perubahan saldo."
    )
    if not settings.simuru_api_key:
        st.warning("SIMURU_API_KEY belum diisi. Sandbox lokal tetap dapat digunakan.")
        st.code("SIMURU_BASE_URL=https://simuru.com/api\nSIMURU_API_KEY=your_key_here")
    elif st.button("Test read-only API connection", type="primary"):
        try:
            with SimuruClient(
                api_key=settings.simuru_api_key, base_url=settings.simuru_base_url
            ) as client:
                profile = client.get_profile()
            st.success("Simuru API connection successful.")
            st.json(
                {
                    "name": profile.get("name"),
                    "status": profile.get("status"),
                    "email": profile.get("email"),
                }
            )
        except (SimuruAPIError, ValueError) as exc:
            st.error(str(exc))
        except Exception:
            st.error("Connection failed. Check network access and API configuration.")
