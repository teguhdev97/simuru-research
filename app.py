from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.engine.runner import BatchRunner
from simuru_research.engine.website_registration_qa import (
    WebsiteRegistrationQAError,
    inspect_registration_form,
)
from simuru_research.providers.simuru_client import SimuruAPIError, SimuruClient
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository
from simuru_research.storage.team_accounts import TeamAccountRegistry
from simuru_research.storage.website_registration import WebsiteRegistrationRepository
from simuru_research.ui.cards import menu_card
from simuru_research.ui.pagination import render_paginated_table
from simuru_research.ui.sneat_theme import (
    inject_sneat_css,
    render_kpi,
    render_page_heading,
    render_topbar,
)

settings = Settings.from_env()
repository = SQLiteRepository(settings.database_path)
team_accounts = TeamAccountRegistry(settings.database_path)
auth_qa_service = LocalAuthQAService(settings.database_path)
website_registration_repository = WebsiteRegistrationRepository(settings.database_path)

st.set_page_config(page_title="Simuru Research", page_icon="🧪", layout="wide")
inject_sneat_css()
render_topbar()

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Overview"

with st.sidebar:
    st.markdown(
        '<div class="sneat-brand" style="padding:.3rem .7rem 1.2rem">✦ simuru</div>',
        unsafe_allow_html=True,
    )
    st.caption("APPS & PAGES")
    nav_items = [
        ("Overview", ":material/dashboard:"),
        ("Mailbox Manager", ":material/mail:"),
        ("Mail list", ":material/mark_email_read:"),
        ("Website Registration", ":material/language:"),
        ("Sandbox Batch", ":material/science:"),
        ("Team Accounts", ":material/group:"),
        ("Run History", ":material/history:"),
        ("SIMURU API", ":material/api:"),
    ]
    for label, icon in nav_items:
        if st.button(
            label,
            icon=icon,
            key=f"nav_{label.lower().replace(' ', '_')}",
            type="primary" if st.session_state["current_page"] == label else "secondary",
            width="stretch",
        ):
            st.session_state["current_page"] = label
            st.rerun()

if st.session_state["current_page"] == "Website Registration":
    render_page_heading("Website Registration", "Testing / Create New Account")
    with menu_card(
        "Authorized website QA",
        "Inspect the registration page. Submission and site challenges remain manual.",
    ):
        target_url = st.text_input(
            "Website registration URL",
            value="https://santrikoding.com/register",
            key="website_registration_target_url",
        )
        allow_confirm = st.checkbox(
            "Saya mengonfirmasi domain ini milik saya atau saya memiliki izin tertulis untuk QA."
        )
    mailbox_emails = [
        str(row["email"])
        for row in auth_qa_service.list_users(limit=500)
        if row.get("email")
    ]
    if st.button("Inspect Website & Prepare QA", type="primary", use_container_width=True):
        if not allow_confirm:
            st.error("Konfirmasi otorisasi target terlebih dahulu.")
        else:
            try:
                with st.spinner("Inspecting registration form..."):
                    inspection = inspect_registration_form(target_url)
                st.session_state["website_registration_inspection"] = inspection
                st.session_state["website_registration_inspected_url"] = target_url
                if not inspection.get("formFound"):
                    st.warning(
                        "Tidak ada form HTML yang terlihat. Jika tombol membuka modal, "
                        "buka form secara manual pada staging dan inspect URL form tersebut."
                    )
                st.success(
                    f"Inspeksi selesai: {len(inspection.get('inputs', []))} input "
                    f"dan {len(inspection.get('buttons', []))} tombol ditemukan."
                )
            except (WebsiteRegistrationQAError, RuntimeError, ValueError) as exc:
                st.error(f"Inspection failed: {exc}")
    inspection = st.session_state.get("website_registration_inspection")
    if inspection:
        with menu_card(
            "Detected registration form",
            "Inspection results only. No registration was submitted.",
        ):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Form", "Found" if inspection.get("formFound") else "Not found")
            m2.metric("Inputs", len(inspection.get("inputs", [])))
            m3.metric("Buttons", len(inspection.get("buttons", [])))
            m4.metric(
                "Challenge",
                "Manual" if inspection.get("challengeDetected") else "Not detected",
            )
            render_paginated_table(
                pd.DataFrame(inspection.get("inputs", [])), key="website_inspected_inputs"
            )
        suggested = inspection.get("suggested_selectors", {})
        if suggested:
            with menu_card("Suggested selectors", "Selector hints for manual QA"):
                render_paginated_table(
                    pd.DataFrame(
                        [
                            {"Field": field, "Selector": selector}
                            for field, selector in suggested.items()
                        ]
                    ),
                    key="website_suggested_selectors",
                )
        target = str(st.session_state.get("website_registration_inspected_url", ""))
        if allow_confirm and target:
            emails = st.text_area(
                "QA email addresses (one per line)",
                value="\n".join(mailbox_emails[:5]),
                help=(
                    "Use only mailbox addresses you control and that are "
                    "approved for the staging environment."
                ),
            )
            if st.button("Save inspection record", key="save_website_qa_record"):
                clean_emails = sorted(
                    {item.strip().lower() for item in emails.splitlines() if item.strip()}
                )
                if not clean_emails:
                    st.error("Masukkan setidaknya satu alamat email QA yang Anda kontrol.")
                else:
                    try:
                        parsed_host = (
                            __import__("urllib.parse", fromlist=["urlparse"])
                            .urlparse(target)
                            .hostname
                            or ""
                        )
                        run_id = website_registration_repository.create_run(
                            target_url=target,
                            website_host=parsed_host,
                            emails=clean_emails,
                        )
                        st.session_state["selected_website_registration_run"] = run_id
                        st.success("QA inspection record saved.")
                    except Exception as exc:
                        st.error(f"Could not save QA record: {exc}")

    st.divider()
    st.markdown("#### Website QA history")
    total = website_registration_repository.count_runs()
    rows = website_registration_repository.list_runs(limit=max(1, total), offset=0)
    selected_ids = []
    if not rows:
        st.markdown(
            '<div class="sneat-card" style="text-align:center;padding:2.5rem">'
            '<div style="font-size:2.8rem;color:#a1acb8">▤</div>'
            '<b>No registration tests yet</b><br>'
            '<span style="color:#a1acb8">Inspect an authorized staging site '
            'to create your first record.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        render_paginated_table(
            pd.DataFrame([
                {
                    "Test Registration Web": row["website_host"],
                    "URL": row["target_url"],
                    "Status": row["status"],
                    "Created": row["created_at"],
                    "Run ID": row["run_id"][:8],
                }
                for row in rows
            ]),
            key="website_registration_history",
        )
        selected_ids = st.multiselect(
            "Open test registration details",
            [row["run_id"] for row in rows],
            default=[row["run_id"] for row in rows[:3]],
            format_func=lambda value: next(
                f'{row["website_host"]} · {row["run_id"][:8]}'
                for row in rows
                if row["run_id"] == value
            ),
            key="website_registration_detail_runs",
        )
    for detail_id in selected_ids:
        detail = website_registration_repository.get_run_detail(str(detail_id))
        if detail:
            with st.expander(f'Registration detail · {detail["website_host"]}', expanded=True):
                st.write(f'**Website:** {detail["target_url"]}')
                st.write(f'**Status:** {detail["status"]}')
                st.write("**Emails used:**")
                render_paginated_table(
                    pd.DataFrame(detail.get("identities", [])),
                    key="website_registration_identities",
                )
                if detail.get("error"):
                    recorded_error = detail["error"]
                    message = (
                        recorded_error.get("message", "A recorded QA error occurred.")
                        if isinstance(recorded_error, dict)
                        else str(recorded_error)
                    )
                    st.warning(message)
elif st.session_state["current_page"] == "Overview":
    render_page_heading("Analytics Dashboard", "Dashboards")
    totals = team_accounts.count_by_type()
    total_team = sum(totals.values())
    qa_count = auth_qa_service.count_users()
    run_count = len(repository.list_runs(limit=500))
    kpis = st.columns(4)
    for col, label, value, foot in zip(
        kpis,
        ["Team Accounts", "Local QA Users", "QA Runs", "Workspace"],
        [str(total_team), str(qa_count), str(run_count), "Ready"],
        ["Owner registry", "Local verification", "Stored history", "Local-first"],
        strict=True,
    ):
        with col:
            render_kpi(label, value, foot)
    overview_left, overview_right = st.columns([1, 2])
    with overview_left:
        with st.container(border=True):
            st.subheader("Congratulations!")
            st.caption("Research workspace overview")
            st.image(
                "https://demos.themeselection.com/sneat-bootstrap-html-admin-template/assets/img/illustrations/prize-light.png",
                alt="Trophy illustration",
                width=150,
            )
    with overview_right:
        st.markdown(
            '<div class="sneat-card"><b>Performance overview</b>'
            '<p style="color:#8592a3">Your research workspace at a glance.</p></div>',
            unsafe_allow_html=True,
        )
    recent = repository.list_runs(limit=8)
    if recent:
        render_paginated_table(pd.DataFrame(recent), key="overview_recent_runs")
    else:
        st.info("No QA runs yet.")
elif st.session_state["current_page"] == "Sandbox Batch":
    render_page_heading("Sandbox Batch", "Testing")
    with menu_card("Run synthetic QA batch", "Configure and launch a local test batch"):
        total_jobs = st.number_input(
            "Synthetic test identities", min_value=1, max_value=100,
            value=min(settings.default_total_jobs, 100), step=1,
        )
        max_workers = st.number_input(
            "Concurrent workers", min_value=1, max_value=10,
            value=min(settings.default_max_workers, 10), step=1,
            help="Bounded local workers. No browser sessions or external signups.",
        )
        st.write(
            "Batch lokal untuk menguji antrean, concurrency, penyimpanan SQLite, "
            "dan ekspor hasil. Data sintetis tidak membuat akun eksternal."
        )
        if st.button("Run sandbox batch", type="primary", use_container_width=True):
            with st.spinner(
                f"Running {total_jobs} synthetic jobs with {max_workers} workers..."
            ):
                summary = BatchRunner(repository).run_batch(
                    total_jobs=int(total_jobs), max_workers=int(max_workers)
                )
            st.success(
                f"Run {summary.run_id[:8]} selesai: "
                f"{summary.passed} passed · {summary.failed} failed."
            )
elif st.session_state["current_page"] == "Mailbox Manager":
    render_page_heading("Mailbox Manager", "Email")
    st.info(
        "Mailbox provisioning pada branch main belum dihubungkan ke dashboard "
        "ini. Kelola mailbox melalui flow cPanel yang tersedia pada instalasi Anda."
    )
elif st.session_state["current_page"] == "Mail list":
    render_page_heading("Mail list", "Email")
    email_rows = [
        {
            "Email": row["email"],
            "Verified": "Yes" if row.get("email_verified") else "No",
            "Created at": row["created_at"],
        }
        for row in auth_qa_service.list_users(limit=10_000)
        if row.get("email")
    ]
    if email_rows:
        with menu_card("QA email addresses", "Addresses stored in the local QA database"):
            render_paginated_table(pd.DataFrame(email_rows), key="mail_list")
    else:
        st.info("No email addresses are registered in the local QA database.")
elif st.session_state["current_page"] == "Team Accounts":
    render_page_heading("Team Accounts", "Workspace")
    counts = team_accounts.count_by_type()
    st.columns(4)[0].metric("Total accounts", sum(counts.values()))
    accounts = team_accounts.list_accounts()
    if accounts:
        render_paginated_table(pd.DataFrame(accounts), key="team_accounts")
    else:
        st.info("Belum ada team account yang tercatat.")
elif st.session_state["current_page"] == "Run History":
    render_page_heading("Run History", "Reports")
    all_runs = repository.list_runs(limit=50)
    if all_runs:
        render_paginated_table(pd.DataFrame(all_runs), key="run_history")
    else:
        st.info("Belum ada riwayat QA.")
elif st.session_state["current_page"] == "SIMURU API":
    render_page_heading("SIMURU API Explorer", "Integrations")
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
            "SIMURU_BASE_URL=https://simuru.com/api\\n"
            "SIMURU_API_KEY=your_api_key_here"
        )
    else:
        st.markdown("**Account information**")
        with st.container(border=True):
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

        st.markdown("**Services & Pricelist**")
        with st.container(border=True):
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
                            render_paginated_table(
                                pd.DataFrame(price_rows), key="simuru_service_prices"
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
                                    render_paginated_table(
                                        pd.DataFrame(filtered.get("data", [])),
                                        key="simuru_filtered_pricelist",
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
                    render_paginated_table(
                        pd.DataFrame(full_rows).head(100),
                        key="simuru_full_pricelist",
                    )
                    st.caption(
                        "Preview limited to the first 100 rows; "
                        "CSV contains all returned rows."
                    )

        st.markdown("**Country Insights**")
        with st.container(border=True):
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
                    render_paginated_table(
                        pd.DataFrame(insight_rows), key="simuru_country_insights"
                    )
