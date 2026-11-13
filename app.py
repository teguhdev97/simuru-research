from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.engine.runner import BatchRunner
from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError
from simuru_research.providers.simuru_client import SimuruAPIError, SimuruClient
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository
from simuru_research.storage.exporter import results_to_csv
from simuru_research.storage.team_accounts import TeamAccountRegistry

settings = Settings.from_env()
repository = SQLiteRepository(settings.database_path)
team_accounts = TeamAccountRegistry(settings.database_path)
auth_qa_service = LocalAuthQAService(settings.database_path)

st.set_page_config(page_title="Simuru Research", page_icon="🧪", layout="wide")
st.title("Simuru Research Lab")
st.caption(
    "Local team registry · SIMURU API research · Registration QA · SQLite history"
)

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
    st.caption("Registration QA uses local-only test identities and a local OTP outbox.")
    st.caption("No Instagram signup, external OTP retrieval, or provider rental is performed.")

overview_tab, team_tab, sandbox_tab, mailbox_tab, registration_qa_tab, history_tab, api_tab = st.tabs(
    [
        "Overview",
        "Team Accounts",
        "Sandbox Batch",
        "Mailbox Manager",
        "Registration QA",
        "Run History & Export",
        "SIMURU API",
    ]
)

with overview_tab:
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
        st.info("Belum ada sandbox run. Buka tab Sandbox Batch untuk menjalankan test identities.")

    st.subheader("Integration scope")
    st.markdown(
        "- Team Accounts: metadata registry for accounts owned by or authorized "
        "for the team to manage.\n"
        "- Instagram API: available for eligible professional Creator/Business "
        "accounts after OAuth.\n"
        "- Personal Instagram accounts: registry-only; no official Instagram API connection.\n"
        "- SIMURU: read-only account and catalog research endpoints.\n"
        "- Registration QA: local signup, email/SMS verification, and login tests only.\n"
        "- No third-party signup, OTP retrieval, or number rental is performed."
    )

with team_tab:
    st.subheader("Team Instagram Account Registry")
    st.write(
        "Catat akun Instagram yang sudah ada dan memang dimiliki atau dikelola "
        "dengan izin oleh tim. Registry ini tidak membuat akun, login, atau "
        "mengambil alih akun Instagram."
    )
    st.warning(
        "Jangan masukkan password, kode OTP, nomor telepon, email pribadi, "
        "session cookie, atau access token ke registry/CSV ini. "
        "Pemilik akun harus menyetujui pencatatan username."
    )

    counts = team_accounts.count_by_type()
    total_accounts = sum(counts.values())
    metric_columns = st.columns(4)
    metric_columns[0].metric("Total registered", total_accounts)
    metric_columns[1].metric("Personal · manual only", counts["personal"])
    metric_columns[2].metric("Creator · OAuth pending", counts["creator"])
    metric_columns[3].metric("Business · OAuth pending", counts["business"])

    with st.form("add_team_account_form", clear_on_submit=True):
        st.markdown("**Register an existing team account**")
        first, second = st.columns(2)
        with first:
            username = st.text_input("Instagram username", placeholder="team_account")
            owner_label = st.text_input("Owner / team label", placeholder="Marketing Team")
        with second:
            account_type = st.selectbox(
                "Account type",
                ["personal", "creator", "business"],
                help=(
                    "Personal accounts are recorded only; official API access "
                    "requires Creator or Business."
                ),
            )
            notes = st.text_input("Notes (optional)", placeholder="Pilot account")
        owner_approved = st.checkbox(
            "I confirm the owner has authorized our team to record and manage this account."
        )
        submitted = st.form_submit_button("Add existing account", type="primary")

    if submitted:
        try:
            inserted = team_accounts.add_account(
                username=username,
                owner_label=owner_label,
                account_type=account_type,
                owner_approved=owner_approved,
                notes=notes,
            )
            if inserted:
                st.success(f"@{username.strip().removeprefix('@')} added to the local registry.")
            else:
                st.info("Username already exists in the registry.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    st.markdown("**Bulk import existing accounts from CSV**")
    st.caption(
        "Required columns: username, owner_label, account_type, owner_approved, notes. "
        "Only rows with owner_approved=true are imported."
    )
    csv_template = (
        "username,owner_label,account_type,owner_approved,notes\n"
        "sample_team_account,Marketing Team,personal,true,Replace with an authorized account\n"
    )
    st.download_button(
        "Download CSV template",
        data=csv_template,
        file_name="simuru-team-accounts-template.csv",
        mime="text/csv",
    )
    uploaded_csv = st.file_uploader(
        "Choose team account CSV",
        type=["csv"],
        key="team_account_csv",
    )
    import_confirmed = st.checkbox(
        "I confirm every imported account is owned by the team or explicitly "
        "authorized by its owner."
    )
    if st.button(
        "Import authorized accounts",
        type="primary",
        disabled=uploaded_csv is None,
    ):
        if not import_confirmed:
            st.error("Confirm account ownership/authorization before importing.")
        else:
            try:
                csv_content = uploaded_csv.getvalue().decode("utf-8-sig")
                result = team_accounts.import_csv(csv_content, confirmed=True)
                st.success(
                    f"Imported: {result['imported']} · "
                    f"Duplicates: {result['duplicates']} · "
                    f"Unapproved skipped: {result['unauthorized']} · "
                    f"Invalid skipped: {result['invalid']}"
                )
                st.rerun()
            except (UnicodeDecodeError, ValueError) as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("Registered team accounts")
    accounts = team_accounts.list_accounts()
    if accounts:
        account_frame = pd.DataFrame(accounts)
        account_frame["owner_approved"] = account_frame["owner_approved"].astype(bool)
        st.dataframe(
            account_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "owner_approved": st.column_config.CheckboxColumn(
                    "Owner approved",
                    disabled=True,
                )
            },
        )
        st.download_button(
            "Export team account registry",
            data=team_accounts.export_csv(),
            file_name="simuru-team-accounts.csv",
            mime="text/csv",
        )
    else:
        st.info("Belum ada akun yang dicatat. Tambahkan satu akun pilot atau import CSV.")

    st.subheader("Meta API eligibility")
    st.markdown(
        "- **Personal:** registry-only. Instagram's official API does not provide "
        "access to consumer/personal accounts.\n"
        "- **Creator / Business:** eligible to proceed to Meta OAuth after the "
        "Instagram API product, permissions, and app roles are configured.\n"
        "- This release does not request passwords, automate sign-up, rent numbers, "
        "retrieve OTPs, or create Instagram accounts."
    )
    st.markdown(
        "[Meta for Developers](https://developers.facebook.com/apps/) · "
        "[Instagram API documentation](https://www.postman.com/meta/instagram/documentation/)"
    )

with sandbox_tab:
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

@st.cache_resource
def get_cpanel_mailbox_manager() -> CpanelBrowserMailboxManager:
    return CpanelBrowserMailboxManager(
        cpanel_url="https://juwana.iixcp.rumahweb.net:2083",
        domain="teguhharits.com",
        prefix="qa",
        quota_mb=50,
    )


with mailbox_tab:
    st.subheader("Mailbox Manager · Rumahweb cPanel")
    st.write(
        "Buat delapan mailbox baru sekaligus pada domain teguhharits.com. "
        "Browser cPanel akan dibuka secara lokal; login dilakukan manual oleh pemilik akun."
    )
    st.info(
        "SIMURU tidak menyimpan password cPanel, cookie, atau cpsess. "
        "Sesi login hanya berada di profil Chromium lokal pada laptop ini."
    )
    try:
        cpanel_manager = get_cpanel_mailbox_manager()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Connect cPanel", type="primary", use_container_width=True):
                current_url = cpanel_manager.connect()
                st.success(
                    "Browser cPanel dibuka. Selesaikan login di jendela Chromium, "
                    "lalu kembali ke tab ini."
                )
        with c2:
            if st.button("Close cPanel browser", use_container_width=True):
                cpanel_manager.close()
                st.info("Browser cPanel ditutup.")
        if st.button(
            "Create 8 New Emails",
            type="primary",
            use_container_width=True,
            key="create_eight_mailboxes",
        ):
            with st.spinner("Memeriksa sesi cPanel dan membuat delapan mailbox..."):
                mailbox_rows = cpanel_manager.create_eight()
            verified_count = sum(row["status"] == "created" for row in mailbox_rows)
            st.success(
                f"Batch selesai: {verified_count}/8 mailbox terverifikasi. "
                "Simpan kredensial sekarang; password hanya ditampilkan pada hasil batch ini."
            )
            mailbox_frame = pd.DataFrame(mailbox_rows)
            st.dataframe(mailbox_frame, use_container_width=True, hide_index=True)
            st.download_button(
                "Download 8 mailbox credentials (CSV)",
                data=mailbox_frame.to_csv(index=False).encode("utf-8"),
                file_name="simuru-eight-mailboxes.csv",
                mime="text/csv",
            )
            st.session_state["latest_mailbox_batch"] = mailbox_rows
        previous_batch = st.session_state.get("latest_mailbox_batch")
        if previous_batch:
            st.caption("Hasil batch terakhir pada sesi dashboard ini:")
            st.dataframe(pd.DataFrame(previous_batch), use_container_width=True, hide_index=True)
    except MailboxError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"cPanel browser error: {type(exc).__name__}: {exc}")

with registration_qa_tab:
    st.subheader("Local Registration + Email/SMS Verification + Login QA")
    st.write(
        "Jalankan workflow registrasi aplikasi internal milik tim. Setiap akun QA "
        "dibuat di SQLite lokal, menerima kode dari local test outbox, memverifikasi "
        "email dan SMS, lalu melakukan login dan memvalidasi session."
    )
    st.warning(
        "Ini adalah aplikasi QA lokal, bukan Instagram. Tidak ada request ke Instagram, "
        "SIMURU number rental, Temp-Mail, Temp-Number, atau layanan pendaftaran pihak ketiga. "
        "Gunakan hanya untuk menguji aplikasi yang dimiliki tim."
    )

    qa_user_count = auth_qa_service.count_users()
    q1, q2, q3 = st.columns(3)
    q1.metric("Local QA users stored", qa_user_count)
    q2.metric("Batch target", 40)
    q3.metric("Default workers", 3)

    qa_col1, qa_col2 = st.columns(2)
    with qa_col1:
        qa_total_jobs = st.number_input(
            "Registration test users",
            min_value=1,
            max_value=100,
            value=40,
            step=1,
            key="registration_qa_total_jobs",
        )
    with qa_col2:
        qa_workers = st.number_input(
            "Concurrent registration workers",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
            key="registration_qa_workers",
        )

    st.caption(
        "Test fixtures use reserved addresses at example.test and fictional "
        "555-0100..0199 phone numbers. Passwords are hashed; OTPs are cleared "
        "from the local outbox after verification."
    )
    st.markdown(
        "**Satu job menjalankan:** register → email OTP → SMS OTP → login → "
        "session validation."
    )

    if st.button(
        "Run registration QA batch",
        type="primary",
        use_container_width=True,
        key="run_registration_qa_batch",
    ):
        try:
            with st.spinner(
                f"Running {qa_total_jobs} local registration flows "
                f"with {qa_workers} workers..."
            ):
                qa_summary = LocalRegistrationQARunner(
                    repository,
                    auth_qa_service,
                ).run_batch(
                    total_jobs=int(qa_total_jobs),
                    max_workers=int(qa_workers),
                )
            st.success(
                f"QA run {qa_summary.run_id[:8]} completed: "
                f"{qa_summary.passed} passed · {qa_summary.failed} failed."
            )
            st.session_state["latest_registration_qa_run"] = qa_summary.run_id
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))

    latest_qa_run = st.session_state.get("latest_registration_qa_run")
    if latest_qa_run:
        qa_results = repository.list_results(latest_qa_run)
        if qa_results:
            passed = sum(row["status"] == "passed" for row in qa_results)
            failed = len(qa_results) - passed
            qa_m1, qa_m2, qa_m3 = st.columns(3)
            qa_m1.metric("Completed jobs", len(qa_results))
            qa_m2.metric("Passed", passed)
            qa_m3.metric("Failed", failed)
            st.dataframe(
                pd.DataFrame(qa_results),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download registration QA results",
                data=results_to_csv(qa_results),
                file_name=f"simuru-registration-qa-{latest_qa_run[:8]}.csv",
                mime="text/csv",
            )

    with st.expander("Inspect local QA users"):
        local_users = auth_qa_service.list_users(limit=100)
        if local_users:
            user_frame = pd.DataFrame(local_users)
            user_frame["email_verified"] = user_frame["email_verified"].astype(bool)
            user_frame["phone_verified"] = user_frame["phone_verified"].astype(bool)
            st.dataframe(
                user_frame,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No local QA users have been created yet.")

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
                    st.caption(
                        "Preview limited to the first 100 rows; "
                        "CSV contains all returned rows."
                    )

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
