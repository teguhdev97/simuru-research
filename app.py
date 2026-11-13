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
st.caption("SIMURU read-only API explorer · Local sandbox QA · SQLite history")

with st.sidebar:
    st.subheader("Sandbox configuration")
    total_jobs = st.number_input(
        "Synthetic test identities",
        min_value=1,
        max_value=100,
        value=min(settings.default_total_jobs, 100),
        step=1,
    )
    max_workers = st.number_input(
        "Concurrent workers",
        min_value=1,
        max_value=10,
        value=min(settings.default_max_workers, 10),
        step=1,
        help="Bounded local workers. No browser sessions or external signups.",
    )
    st.divider()
    st.caption("Sandbox identities are fictional and never sent to SIMURU.")
    st.caption("SIMURU integration below is restricted to read-only account/catalog endpoints.")

overview_tab, sandbox_tab, history_tab, api_tab = st.tabs(
    ["Overview", "Sandbox Batch", "Run History & Export", "SIMURU API"]
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
            st.dataframe(
                pd.DataFrame(latest_results),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Belum ada sandbox run. Buka tab Sandbox Batch untuk menjalankan test identities.")

    st.subheader("Integration scope")
    st.markdown(
        "- Account: profile and balance.\n"
        "- Catalog: services, countries, price list, operators, and offers.\n"
        "- Insights: country-level success-rate summary.\n"
        "- No order creation/cancellation, number rental, email rental, or OTP retrieval."
    )

with sandbox_tab:
    st.subheader("Run synthetic QA batch")
    st.write(
        "Batch lokal untuk menguji antrean, concurrency, penyimpanan SQLite, "
        "dan ekspor hasil. Tidak membuat akun eksternal dan tidak menghubungi penyedia SMS."
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
            st.dataframe(
                pd.DataFrame(selected_results),
                use_container_width=True,
                hide_index=True,
            )

with api_tab:
    st.subheader("SIMURU API Explorer")
    st.caption(
        "Base URL: https://simuru.com/api · Authentication: X-API-KEY header"
    )
    st.info(
        "Explorer ini hanya memanggil endpoint GET yang bersifat baca-saja. "
        "Endpoint transaksi seperti membuat order, membatalkan order, menyewa nomor, "
        "atau mengambil OTP tidak disediakan."
    )

    if not settings.simuru_api_key:
        st.warning("SIMURU_API_KEY belum diisi. Sandbox lokal tetap dapat digunakan.")
        st.code(
            "SIMURU_BASE_URL=https://simuru.com/api\n"
            "SIMURU_API_KEY=your_api_key_here"
        )
    else:
        account_tab, catalog_tab, insights_tab = st.tabs(
            ["Account", "Services & Pricelist", "Country Insights"]
        )

        with account_tab:
            st.write("Periksa profil akun dan saldo SIMURU.")
            if st.button("Refresh account information", key="simuru_account_refresh"):
                try:
                    with SimuruClient(
                        api_key=settings.simuru_api_key,
                        base_url=settings.simuru_base_url,
                    ) as client:
                        profile = client.get_profile()
                        balance = client.get_balance()
                    st.session_state["simuru_account"] = {
                        "profile": profile,
                        "balance": balance,
                    }
                    st.success("Account information loaded.")
                except (SimuruAPIError, ValueError) as exc:
                    st.error(str(exc))

            account = st.session_state.get("simuru_account")
            if account:
                profile = account["profile"]
                balance = account["balance"]
                c1, c2, c3 = st.columns(3)
                c1.metric("Account", profile.get("name", "—"))
                c2.metric("Status", profile.get("status", "—"))
                c3.metric(
                    "Balance",
                    balance.get("balance_formatted", balance.get("balance", "—")),
                )
                st.json(
                    {
                        "id": profile.get("id"),
                        "name": profile.get("name"),
                        "email": profile.get("email"),
                        "status": profile.get("status"),
                    }
                )

        with catalog_tab:
            st.write(
                "Muat metadata layanan dan negara, lalu telusuri harga per layanan. "
                "Full pricelist dapat berisi ribuan baris; hasilnya bisa diekspor ke CSV."
            )
            if st.button("Load services and countries", key="simuru_catalog_load"):
                try:
                    with SimuruClient(
                        api_key=settings.simuru_api_key,
                        base_url=settings.simuru_base_url,
                    ) as client:
                        st.session_state["simuru_services"] = client.get_services()
                        st.session_state["simuru_countries"] = client.get_countries()
                    st.success("Services and countries loaded.")
                except (SimuruAPIError, ValueError) as exc:
                    st.error(str(exc))

            services = st.session_state.get("simuru_services", [])
            if services:
                service_options = {}
                for service in services:
                    service_id = service.get("service_id", service.get("id"))
                    if service_id is not None:
                        label = (
                            f"{service.get('service_name', 'Service')} "
                            f"({service_id})"
                        )
                        service_options[label] = service_id

                if service_options:
                    selected_service_label = st.selectbox(
                        "Service",
                        list(service_options),
                        key="simuru_service_select",
                    )
                    selected_service_id = service_options[selected_service_label]

                    if st.button(
                        "Load countries and prices for service",
                        key="simuru_service_prices_load",
                    ):
                        try:
                            with SimuruClient(
                                api_key=settings.simuru_api_key,
                                base_url=settings.simuru_base_url,
                            ) as client:
                                service_payload = client.get_service_countries(
                                    selected_service_id
                                )
                            st.session_state["simuru_service_prices"] = {
                                "service_id": str(selected_service_id),
                                "payload": service_payload,
                            }
                        except (SimuruAPIError, ValueError) as exc:
                            st.error(str(exc))

                    service_prices = st.session_state.get("simuru_service_prices")
                    if (
                        service_prices
                        and service_prices["service_id"] == str(selected_service_id)
                    ):
                        payload = service_prices["payload"]
                        price_rows = payload.get("data", [])
                        if price_rows:
                            st.dataframe(
                                pd.DataFrame(price_rows),
                                use_container_width=True,
                                hide_index=True,
                            )
                            if payload.get("ranking_note"):
                                st.caption(payload["ranking_note"])

                            country_options = {}
                            for row in price_rows:
                                country_id = row.get("country_id")
                                if country_id is not None:
                                    country_name = row.get(
                                        "country_name", f"Country {country_id}"
                                    )
                                    country_iso = row.get("country_iso", "")
                                    label = f"{country_name} {country_iso} (ID {country_id})"
                                    country_options[label] = int(country_id)

                            if country_options:
                                selected_country_label = st.selectbox(
                                    "Country",
                                    list(country_options),
                                    key="simuru_country_select",
                                )
                                selected_country_id = country_options[
                                    selected_country_label
                                ]

                                op_col, offer_col = st.columns(2)
                                with op_col:
                                    if st.button(
                                        "Load operators",
                                        key="simuru_operators_load",
                                        use_container_width=True,
                                    ):
                                        try:
                                            with SimuruClient(
                                                api_key=settings.simuru_api_key,
                                                base_url=settings.simuru_base_url,
                                            ) as client:
                                                st.session_state["simuru_operators"] = (
                                                    client.get_operators(
                                                        selected_service_id,
                                                        selected_country_id,
                                                    )
                                                )
                                            st.success("Operators loaded.")
                                        except (SimuruAPIError, ValueError) as exc:
                                            st.error(str(exc))

                                with offer_col:
                                    if st.button(
                                        "Load price offers",
                                        key="simuru_offers_load",
                                        use_container_width=True,
                                    ):
                                        try:
                                            with SimuruClient(
                                                api_key=settings.simuru_api_key,
                                                base_url=settings.simuru_base_url,
                                            ) as client:
                                                st.session_state["simuru_offers"] = (
                                                    client.get_offers(
                                                        selected_service_id,
                                                        selected_country_id,
                                                    )
                                                )
                                            st.success("Price offers loaded.")
                                        except (SimuruAPIError, ValueError) as exc:
                                            st.error(str(exc))

                                operators = st.session_state.get("simuru_operators")
                                if operators:
                                    st.markdown("**Operators**")
                                    st.json(operators)

                                offers = st.session_state.get("simuru_offers")
                                if offers:
                                    st.markdown("**Price offers**")
                                    st.json(offers)

                                if st.button(
                                    "Load filtered pricelist",
                                    key="simuru_filtered_pricelist",
                                ):
                                    try:
                                        with SimuruClient(
                                            api_key=settings.simuru_api_key,
                                            base_url=settings.simuru_base_url,
                                        ) as client:
                                            st.session_state["simuru_filtered_pricelist"] = (
                                                client.get_pricelist(
                                                    service_id=selected_service_id,
                                                    country_id=selected_country_id,
                                                )
                                            )
                                        st.success("Filtered pricelist loaded.")
                                    except (SimuruAPIError, ValueError) as exc:
                                        st.error(str(exc))

                                filtered = st.session_state.get(
                                    "simuru_filtered_pricelist"
                                )
                                if filtered:
                                    st.dataframe(
                                        pd.DataFrame(filtered.get("data", [])),
                                        use_container_width=True,
                                        hide_index=True,
                                    )

            st.divider()
            if st.button(
                "Load complete pricelist",
                key="simuru_full_pricelist",
                help="Fetches the complete service × country catalog in one request.",
            ):
                try:
                    with SimuruClient(
                        api_key=settings.simuru_api_key,
                        base_url=settings.simuru_base_url,
                    ) as client:
                        st.session_state["simuru_full_pricelist"] = (
                            client.get_pricelist()
                        )
                    st.success("Complete pricelist loaded.")
                except (SimuruAPIError, ValueError) as exc:
                    st.error(str(exc))

            full_pricelist = st.session_state.get("simuru_full_pricelist")
            if full_pricelist:
                full_rows = full_pricelist.get("data", [])
                meta = full_pricelist.get("meta", {})
                st.metric("Pricelist rows", meta.get("total", len(full_rows)))
                st.caption(f"Generated at: {meta.get('generated_at', 'Unknown')}")
                if full_rows:
                    st.download_button(
                        "Download full pricelist CSV",
                        data=pd.DataFrame(full_rows).to_csv(index=False),
                        file_name="simuru-pricelist.csv",
                        mime="text/csv",
                    )
                    st.dataframe(
                        pd.DataFrame(full_rows).head(100),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption("Preview limited to the first 100 rows; CSV contains all returned rows.")

        with insights_tab:
            st.write(
                "Ringkasan negara berdasarkan success rate layanan selama periode "
                "yang disediakan oleh SIMURU."
            )
            if st.button(
                "Load country insights",
                key="simuru_insights_load",
            ):
                try:
                    with SimuruClient(
                        api_key=settings.simuru_api_key,
                        base_url=settings.simuru_base_url,
                    ) as client:
                        st.session_state["simuru_insights"] = (
                            client.get_country_insights()
                        )
                    st.success("Country insights loaded.")
                except (SimuruAPIError, ValueError) as exc:
                    st.error(str(exc))

            insights = st.session_state.get("simuru_insights")
            if insights:
                st.caption(
                    f"Window: {insights.get('window_hours', '—')} hours · "
                    f"Generated: {insights.get('generated_at', '—')}"
                )
                insight_rows = []
                for service in insights.get("services", []):
                    insight_rows.append(
                        {
                            "service": service.get("service_name"),
                            "success_rate": service.get("success_rate"),
                            "best_country": service.get("best_country"),
                            "best_success_rate": service.get("best_success_rate"),
                        }
                    )
                if insight_rows:
                    st.dataframe(
                        pd.DataFrame(insight_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
