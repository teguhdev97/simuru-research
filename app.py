from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.engine.runner import BatchRunner
from simuru_research.engine.website_registration_qa import (
    WebsiteRegistrationQAError,
    inspect_registration_form,
    validate_registration_target,
)
from simuru_research.providers.simuru_client import SimuruAPIError, SimuruClient
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository
from simuru_research.storage.exporter import results_to_csv
from simuru_research.storage.team_accounts import TeamAccountRegistry
from simuru_research.storage.website_registration import WebsiteRegistrationRepository
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
st.markdown('<div class="sneat-page-title">Analytics Dashboard</div><div class="sneat-breadcrumb">Home / Overview</div>', unsafe_allow_html=True)
st.caption("Research workspace · Mailbox services · Website QA · Local persistence")

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

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Overview"

with st.sidebar:
    st.markdown(
        '<div class="sneat-brand" style="padding:.3rem .7rem 1.2rem">✦ simuru</div>',
        unsafe_allow_html=True,
    )
    st.caption("WORKSPACE")
    nav_items = [
        ("Overview", "⌂"),
        ("Mailbox Manager", "✉"),
        ("Website Registration", "＋"),
        ("Sandbox Batch", "▦"),
        ("Team Accounts", "♙"),
        ("Run History", "◷"),
        ("SIMURU API", "⌘"),
    ]
    for label, icon in nav_items:
        if st.button(
            f"{icon}   {label}",
            key=f"nav_{label.lower().replace(' ', '_')}",
            type="primary" if st.session_state["current_page"] == label else "secondary",
            use_container_width=True,
        ):
            st.session_state["current_page"] = label
            st.rerun()

overview_tab = team_tab = sandbox_tab = mailbox_tab = website_tab = registration_qa_tab = history_tab = api_tab = None
if False:
    overview_tab = None
with overview_tab:
    render_page_heading("Analytics Dashboard", "Dashboards")
    runs = repository.list_runs(limit=1)
    counts = team_accounts.count_by_type()
    account_total = sum(counts.values())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi("Team Accounts", f"{account_total:,}", "Registry overview")
    with c2:
        render_kpi("Personal", f'{counts["personal"]:,}', "Manual only")
    with c3:
        render_kpi("Creator", f'{counts["creator"]:,}', "OAuth pending")
    with c4:
        render_kpi("Business", f'{counts["business"]:,}', "OAuth pending")

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


if st.session_state["current_page"] == "Website Registration":
    render_page_heading("Website Registration", "Testing / Create New Account")
    st.markdown(
        '<div class="sneat-card"><b>Authorized Website QA</b><br>'
        '<span style="color:#8592a3">Inspect a local or allowlisted staging registration page. '
        'CAPTCHA and consent controls remain manual.</span></div>',
        unsafe_allow_html=True,
    )
    target_url = st.text_input(
        "Website registration URL",
        placeholder="https://staging.your-domain.test/register",
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
                detail = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                st.error("Inspection failed")
                st.code(__import__("json").dumps(detail, indent=2, ensure_ascii=False), language="json")
    inspection = st.session_state.get("website_registration_inspection")
    if inspection:
        st.markdown("#### Detected registration form")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Form", "Found" if inspection.get("formFound") else "Not found")
        m2.metric("Inputs", len(inspection.get("inputs", [])))
        m3.metric("Buttons", len(inspection.get("buttons", [])))
        m4.metric("Challenge", "Manual" if inspection.get("challengeDetected") else "Not detected")
        st.dataframe(
            pd.DataFrame(inspection.get("inputs", [])),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Selector suggestions are inspection metadata only; no registration is submitted.")
        suggested = inspection.get("suggested_selectors", {})
        st.json(suggested)
        target = str(st.session_state.get("website_registration_inspected_url", ""))
        if allow_confirm and target:
            emails = st.text_area(
                "QA email addresses (one per line)",
                value="\n".join(mailbox_emails[:5]),
                help="Use only mailbox addresses you control and that are approved for the staging environment.",
            )
            if st.button("Save QA test record", key="save_website_qa_record"):
                clean_emails = sorted({item.strip().lower() for item in emails.splitlines() if item.strip()})
                if not clean_emails:
                    st.error("Masukkan setidaknya satu alamat email QA yang Anda kontrol.")
                else:
                    try:
                        parsed_host = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(target).hostname or ""
                        run_id = website_registration_repository.create_run(
                            target_url=target,
                            website_host=parsed_host,
                            emails=clean_emails,
                        )
                        st.session_state["selected_website_registration_run"] = run_id
                        st.success("QA inspection record saved.")
                    except Exception as exc:
                        st.error(__import__("json").dumps({
                            "type": type(exc).__name__,
                            "message": str(exc),
                        }, indent=2, ensure_ascii=False))

    st.divider()
    st.markdown("#### Website QA history")
    page_size = 8
    page_key = "website_registration_page"
    total = website_registration_repository.count_runs()
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(int(st.session_state.get(page_key, 1)), total_pages)
    rows = website_registration_repository.list_runs(
        limit=page_size, offset=(current_page - 1) * page_size
    )
    if not rows:
        st.markdown(
            '<div class="sneat-card" style="text-align:center;padding:2.5rem">'
            '<div style="font-size:2.8rem;color:#a1acb8">▤</div>'
            '<b>No registration tests yet</b><br>'
            '<span style="color:#a1acb8">Inspect an authorized staging site to create your first record.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.dataframe(
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
            use_container_width=True,
            hide_index=True,
        )
        selected_id = st.selectbox(
            "Open test registration details",
            [row["run_id"] for row in rows],
            format_func=lambda value: next(
                f'{row["website_host"]} · {row["run_id"][:8]}' for row in rows if row["run_id"] == value
            ),
        )
        if st.button("View details", key="open_website_registration_detail"):
            st.session_state["selected_website_registration_run"] = selected_id
        prev_col, page_col, next_col = st.columns([1, 2, 1])
        with prev_col:
            if st.button("← Previous", disabled=current_page <= 1):
                st.session_state[page_key] = current_page - 1
                st.rerun()
        with page_col:
            st.caption(f"Page {current_page} of {total_pages} · {total} records")
        with next_col:
            if st.button("Next →", disabled=current_page >= total_pages):
                st.session_state[page_key] = current_page + 1
                st.rerun()
    detail_id = st.session_state.get("selected_website_registration_run")
    if detail_id:
        detail = website_registration_repository.get_run_detail(str(detail_id))
        if detail:
            with st.expander("Registration detail", expanded=True):
                st.write(f'**Website:** {detail["target_url"]}')
                st.write(f'**Status:** {detail["status"]}')
                st.write("**Emails used:**")
                st.dataframe(
                    pd.DataFrame(detail.get("identities", [])),
                    use_container_width=True,
                    hide_index=True,
                )
                if detail.get("error"):
                    st.code(
                        __import__("json").dumps(detail["error"], indent=2, ensure_ascii=False),
                        language="json",
                    )
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
    st.markdown('<div class="sneat-card"><b>Performance overview</b><p style="color:#8592a3">Your research workspace at a glance.</p></div>', unsafe_allow_html=True)
    recent = repository.list_runs(limit=8)
    if recent:
        st.dataframe(pd.DataFrame(recent), use_container_width=True, hide_index=True)
    else:
        st.info("No QA runs yet.")
elif st.session_state["current_page"] == "Sandbox Batch":
    render_page_heading("Sandbox Batch", "Testing")
    st.info("Gunakan tab lama pada bagian Sandbox Batch untuk konfigurasi dan hasil. UI sidebar ini sedang menjadi entrypoint baru.")
elif st.session_state["current_page"] == "Mailbox Manager":
    render_page_heading("Mailbox Manager", "Email")
    st.info("Mailbox management tetap tersedia melalui alur CLI yang sudah ada pada rilis main.")
elif st.session_state["current_page"] == "Team Accounts":
    render_page_heading("Team Accounts", "Workspace")
    st.info("Team registry tersedia di penyimpanan lokal.")
elif st.session_state["current_page"] == "Run History":
    render_page_heading("Run History", "Reports")
    all_runs = repository.list_runs(limit=50)
    st.dataframe(pd.DataFrame(all_runs), use_container_width=True, hide_index=True)
elif st.session_state["current_page"] == "SIMURU API":
    render_page_heading("SIMURU API Explorer", "Integrations")
    st.info("API Explorer tetap tersedia pada halaman tab lama selama migrasi.")

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
