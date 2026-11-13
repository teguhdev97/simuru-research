from __future__ import annotations

import os
import pandas as pd
import streamlit as st

from simuru_research.config.google_oauth_qa import (
    GoogleOAuthQAConfigError,
    GoogleOAuthQAConfigStore,
)
from simuru_research.config.settings import Settings
from simuru_research.config.website_profiles import (
    WebsiteProfileError,
    WebsiteProfileStore,
    profile_registration_url,
)
from simuru_research.engine.form_inspector import FormInspectionError, inspect_form
from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.engine.runner import BatchRunner
from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import ImapOTPReader, MailboxError, MailboxSettings, SmtpMailboxSender
from simuru_research.security.mailbox_vault import MailboxCredentialVault
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

overview_tab, team_tab, sandbox_tab, mailbox_tab, website_tab, registration_qa_tab, history_tab, api_tab = st.tabs(
    [
        "Overview",
        "Team Accounts",
        "Sandbox Batch",
        "Mailbox Manager",
        "Website Automation",
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

with mailbox_tab:
    st.subheader("Mailbox Manager · Rumahweb cPanel")
    st.write(
        "Buat tepat lima mailbox baru pada domain teguhharits.com. "
        "Status login cPanel diperbarui otomatis setelah kamu login di Chromium."
    )
    st.info(
        "Mode browser-session tidak memerlukan cPanel API Token. "
        "Password cPanel dan cpsess tidak disimpan di .env atau GitHub."
    )
    env_mailbox_password = os.getenv("QA_MAILBOX_MASTER_PASSWORD", "").strip()
    mailbox_password_input = st.text_input(
        "Shared QA mailbox password (optional)",
        value=env_mailbox_password,
        type="password",
        placeholder="Kosongkan untuk password acak unik",
        help=(
            "Isi password QA pilihan untuk menyamakan password sementara. "
            "Field ini hanya berada di sesi dashboard; .env lokal lebih cocok untuk konfigurasi tetap."
        ),
        key="qa_mailbox_password_input",
    ).strip()
    if not mailbox_password_input and not st.session_state.get("mailbox_password_notice_dismissed", False):
        with st.container(border=True):
            notice_col, dismiss_col = st.columns([8, 1])
            with notice_col:
                st.warning(
                    "Password seragam belum diatur. Pembuatan tetap bisa berjalan dengan "
                    "password acak dan unik untuk setiap mailbox; kredensial tersedia melalui CSV."
                )
            with dismiss_col:
                if st.button("Dismiss", key="dismiss_mailbox_password_notice"):
                    st.session_state["mailbox_password_notice_dismissed"] = True
                    st.rerun()

    cpanel_manager = CpanelBrowserMailboxManager(
        cpanel_url="https://juwana.iixcp.rumahweb.net:2083",
        domain="teguhharits.com",
        prefix="qa",
        quota_mb=50,
        mailbox_password=mailbox_password_input,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Connect cPanel", type="primary", use_container_width=True):
            try:
                st.info(cpanel_manager.connect())
                st.rerun()
            except MailboxError as exc:
                st.error(str(exc))
    with c2:
        if st.button("Logout & Close cPanel", use_container_width=True):
            logout = cpanel_manager.close()
            if logout["server_logout_confirmed"] == "true":
                st.success(logout["message"])
            else:
                st.warning(logout["message"])

    @st.fragment(run_every="3s")
    def render_mailbox_workflow():
        status = cpanel_manager.session_status()
        st.session_state["cpanel_session_status"] = status
        session_ready = bool(status.get("connected"))
        if session_ready:
            st.success(
                "cPanel login terdeteksi dan UAPI Email::list_pops berhasil. "
                "Pembuatan lima mailbox sudah diaktifkan."
            )
        else:
            st.warning(status.get("message", "Menunggu login cPanel..."))

        diagnostics = status.get("diagnostics", [])
        if diagnostics:
            with st.expander("Detail diagnostik UAPI (session ID disamarkan)"):
                st.json(diagnostics)

        st.markdown("**Existing QA mailboxes**")
        if st.button("Refresh existing mailbox list", key="refresh_existing_mailboxes"):
            try:
                st.session_state["existing_qa_mailboxes"] = cpanel_manager.list_domain_mailboxes()
                st.session_state["mailbox_workflow_alert"] = {
                    "kind": "success",
                    "message": (
                        f"Ditemukan {len(st.session_state['existing_qa_mailboxes'])} mailbox "
                        f"dengan prefix {cpanel_manager.prefix} pada domain {cpanel_manager.domain}."
                    ),
                }
            except MailboxError as exc:
                st.session_state["mailbox_workflow_alert"] = {
                    "kind": "error",
                    "message": str(exc),
                }

        existing_qa_mailboxes = st.session_state.get("existing_qa_mailboxes", [])
        if existing_qa_mailboxes:
            selected_existing_mailboxes = st.multiselect(
                "Pilih mailbox lama yang ingin disamakan password-nya",
                options=existing_qa_mailboxes,
                max_selections=5,
                key="selected_existing_qa_mailboxes",
            )
            if mailbox_password_input and selected_existing_mailboxes:
                if st.button(
                    "Set same password for selected existing mailboxes",
                    key="reset_selected_existing_mailboxes",
                    use_container_width=True,
                ):
                    try:
                        with st.spinner("Memperbarui password mailbox terpilih..."):
                            reset_rows = cpanel_manager.reset_mailbox_passwords(
                                selected_existing_mailboxes
                            )
                        if reset_rows and all(row["status"] == "updated" for row in reset_rows):
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "success",
                                "message": (
                                    f"Password berhasil diperbarui untuk {len(reset_rows)} mailbox. "
                                    "Simpan password ini dengan aman."
                                ),
                            }
                        else:
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "error",
                                "message": "Sebagian mailbox gagal diubah: " + str(reset_rows),
                            }
                    except MailboxError as exc:
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "error",
                            "message": str(exc),
                        }
        elif session_ready:
            st.caption("Klik Refresh existing mailbox list untuk memuat mailbox QA yang sudah ada.")

        if st.button(
            "Create 5 New Emails",
            type="primary",
            use_container_width=True,
            key="create_five_mailboxes",
            disabled=not session_ready,
        ):
            st.session_state.pop("latest_mailbox_batch", None)
            try:
                with st.spinner("Membuat tepat lima mailbox dan memverifikasi hasilnya..."):
                    mailbox_rows = cpanel_manager.create_five()
                st.session_state["latest_mailbox_batch"] = mailbox_rows
                successful = sum(row.get("status") == "created" for row in mailbox_rows)
                if successful == 5 and len(mailbox_rows) == 5:
                    st.session_state["mailbox_workflow_alert"] = {
                        "kind": "success",
                        "message": "Berhasil membuat dan memverifikasi kelima mailbox.",
                    }
                else:
                    st.session_state["mailbox_workflow_alert"] = {
                        "kind": "error",
                        "message": (
                            f"Baru {successful}/5 mailbox terverifikasi. "
                            "Tahap Google OAuth belum dibuka. Periksa tabel hasil."
                        ),
                    }
            except MailboxError as exc:
                st.session_state["mailbox_workflow_alert"] = {
                    "kind": "error",
                    "message": str(exc),
                }

        alert = st.session_state.get("mailbox_workflow_alert")
        if alert:
            if alert.get("kind") == "error":
                st.error(alert.get("message", "Mailbox operation failed."))
            elif alert.get("kind") == "success":
                st.success(alert.get("message", "Mailbox operation completed."))
            if st.button("Dismiss alert", key="dismiss_mailbox_workflow_alert"):
                st.session_state.pop("mailbox_workflow_alert", None)
                st.rerun()

        mailbox_rows = st.session_state.get("latest_mailbox_batch", [])
        for mailbox_row in mailbox_rows:
            if mailbox_row.get("status") == "created" and MailboxCredentialVault().get(
                str(mailbox_row["email"])
            ):
                mailbox_row["credential_storage"] = "saved"
        st.session_state["latest_mailbox_batch"] = mailbox_rows
        batch_complete = (
            len(mailbox_rows) == 5
            and all(
                row.get("status") == "created"
                and row.get("credential_storage") == "saved"
                for row in mailbox_rows
            )
        )
        if mailbox_rows:
            mailbox_frame = pd.DataFrame(mailbox_rows)
            st.dataframe(
                mailbox_frame[[column for column in ["email", "status", "credential_storage", "error"] if column in mailbox_frame.columns]],
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download 5 mailbox credentials (CSV)",
                data=mailbox_frame.to_csv(index=False).encode("utf-8"),
                file_name="simuru-five-mailboxes.csv",
                mime="text/csv",
            )
            if mailbox_password_input:
                if st.button("Set same password for these 5 mailboxes", use_container_width=True):
                    try:
                        with st.spinner("Memperbarui password mailbox di cPanel..."):
                            reset_rows = cpanel_manager.reset_mailbox_passwords(
                                [str(row["email"]) for row in mailbox_rows if row.get("status") == "created"]
                            )
                        st.session_state["mailbox_password_reset"] = reset_rows
                        if reset_rows and all(row["status"] == "updated" for row in reset_rows):
                            for mailbox_row in mailbox_rows:
                                if mailbox_row.get("status") == "created":
                                    mailbox_row["password"] = mailbox_password_input
                            st.session_state["latest_mailbox_batch"] = mailbox_rows
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "success",
                                "message": "Password mailbox berhasil diseragamkan. Download ulang CSV agar berisi password terbaru.",
                            }
                        else:
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "error",
                                "message": "Sebagian password belum berhasil diperbarui: " + str(reset_rows),
                            }
                    except MailboxError as exc:
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "error",
                            "message": str(exc),
                        }
            else:
                st.info("Password acak unik sedang digunakan. Isi field Shared QA mailbox password untuk menyamakan password kelima mailbox.")

        with st.expander("Import existing mailbox password from CSV", expanded=False):
            st.caption(
                "Gunakan untuk mailbox yang telah dibuat sebelumnya. Password hanya disimpan "
                "di Windows Credential Manager lokal, bukan SQLite atau Git."
            )
            old_email = st.text_input(
                "Existing QA mailbox email",
                placeholder=f"{cpanel_manager.prefix}-xxxx-01@{cpanel_manager.domain}",
                key="vault_import_email",
            ).strip().lower()
            old_password = st.text_input(
                "Mailbox password from CSV",
                type="password",
                key="vault_import_password",
            )
            if st.button("Save password to local credential vault", key="vault_import_save"):
                try:
                    cpanel_manager.import_mailbox_credential(old_email, old_password)
                    st.session_state["mailbox_workflow_alert"] = {
                        "kind": "success",
                        "message": "Mailbox password tersimpan di Windows Credential Manager.",
                    }
                except (MailboxError, RuntimeError) as exc:
                    st.session_state["mailbox_workflow_alert"] = {
                        "kind": "error",
                        "message": str(exc),
                    }


        if batch_complete:
            st.divider()
            st.subheader("Mailbox connectivity & OTP")
            st.caption(
                "IMAP dipakai untuk membaca OTP masuk. SMTP hanya dibutuhkan bila SIMURU perlu mengirim email."
            )
            imap_ready = all(
                MailboxCredentialVault().get(str(row["email"]))
                for row in mailbox_rows
            )
            if imap_ready:
                st.success("Kelima password mailbox tersedia di Windows Credential Manager.")
                mailbox_for_otp = st.selectbox(
                    "Mailbox untuk menerima OTP",
                    [str(row["email"]) for row in mailbox_rows],
                    key="otp_mailbox_selected",
                )
                otp_sender_allowlist = os.getenv("QA_OTP_ALLOWED_SENDERS", "").strip()
                if not otp_sender_allowlist:
                    st.warning(
                        "Atur QA_OTP_ALLOWED_SENDERS pada .env dengan sender yang diharapkan "
                        "pada lingkungan staging milikmu."
                    )
                if st.button("Check IMAP connection", key="check_imap_connection"):
                    try:
                        mailbox_settings = MailboxSettings.from_env()
                        mailbox_settings = __import__("dataclasses").replace(
                            mailbox_settings,
                            domain=cpanel_manager.domain,
                            prefix=cpanel_manager.prefix,
                            mailbox_passwords={
                                str(row["email"]).lower(): str(row.get("password", ""))
                                for row in mailbox_rows
                                if row.get("status") == "created"
                            },
                        )
                        reader = ImapOTPReader(mailbox_settings)
                        reader.check_connection(mailbox_for_otp)
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "success",
                            "message": "IMAP login berhasil dan folder INBOX dapat dibuka.",
                        }
                    except MailboxError as exc:
                        message = str(exc)
                        if "No matching fresh OTP" in message:
                            message = (
                                "Koneksi IMAP dan autentikasi kemungkinan berhasil, "
                                "tetapi belum ada OTP baru dalam inbox pada waktu pemeriksaan."
                            )
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "error",
                            "message": message,
                        }
                otp_timeout = st.number_input(
                    "OTP wait timeout (seconds)",
                    min_value=10,
                    max_value=180,
                    value=60,
                    step=5,
                )
                if st.button("Wait for fresh verification code", key="wait_for_mailbox_otp"):
                    try:
                        from datetime import UTC, datetime

                        mailbox_settings = MailboxSettings.from_env()
                        mailbox_settings = __import__("dataclasses").replace(
                            mailbox_settings,
                            domain=cpanel_manager.domain,
                            prefix=cpanel_manager.prefix,
                            mailbox_passwords={
                                str(row["email"]).lower(): str(row.get("password", ""))
                                for row in mailbox_rows
                                if row.get("status") == "created"
                            },
                        )
                        reader = ImapOTPReader(mailbox_settings)
                        st.session_state["last_mailbox_otp"] = reader.wait_for_otp(
                            mailbox_for_otp,
                            since=datetime.now(UTC),
                            timeout_seconds=int(otp_timeout),
                        )
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "success",
                            "message": "Kode verifikasi baru berhasil diterima dari mailbox.",
                        }
                    except MailboxError as exc:
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "error",
                            "message": str(exc),
                        }
                if st.session_state.get("last_mailbox_otp"):
                    st.code(st.session_state["last_mailbox_otp"])
                    if st.button("Clear displayed OTP", key="clear_mailbox_otp"):
                        st.session_state.pop("last_mailbox_otp", None)
                        st.rerun()
            else:
                st.warning(
                    "Password mailbox belum semuanya tersimpan di Windows Credential Manager. "
                    "Import password dari CSV satu per satu sebelum IMAP dapat digunakan."
                )

        if batch_complete:
            st.divider()
            st.subheader("Google OAuth Registration QA")
            st.success("Lima mailbox berhasil dibuat dan diverifikasi.")
            test_emails = [str(row["email"]) for row in mailbox_rows]
            st.caption("Setiap alamat harus sudah menjadi Google Account dan ditambahkan ke Google Auth Platform → Audience → Test users.")
            st.code("\\n".join(test_emails), language="text")
            with st.form("integrated_google_oauth_qa_form"):
                target_url = st.text_input("Website registration URL", placeholder="https://your-staging-site.example/register")
                selected_test_email = st.selectbox("Google test account", test_emails)
                owns_target = st.checkbox("Saya memiliki website ini atau memiliki izin eksplisit untuk menjalankan QA.")
                accounts_ready = st.checkbox("Kelima alamat sudah menjadi Google Account dan ditambahkan ke OAuth Test Users.")
                inspect_and_save = st.form_submit_button("Inspect website & prepare Google OAuth test", type="primary", use_container_width=True)
            if inspect_and_save:
                if not owns_target:
                    st.error("Konfirmasi kepemilikan/izin website sebelum menjalankan QA.")
                elif not accounts_ready:
                    st.error("Selesaikan pembuatan Google Account dan penambahan Test Users terlebih dahulu.")
                else:
                    try:
                        with st.spinner("Memeriksa halaman registrasi dan tombol Google OAuth..."):
                            inspection = inspect_form(target_url)
                        st.session_state["integrated_oauth_target"] = target_url
                        st.session_state["integrated_oauth_inspection"] = inspection
                        st.session_state["integrated_oauth_email"] = selected_test_email
                        st.success(f"Halaman diperiksa: {inspection.get('title') or inspection.get('url')}. {len(inspection.get('google_buttons', []))} kontrol Google terdeteksi.")
                    except FormInspectionError as exc:
                        st.error(str(exc))
            oauth_inspection = st.session_state.get("integrated_oauth_inspection")
            if oauth_inspection:
                google_controls = oauth_inspection.get("google_buttons", [])
                if google_controls:
                    st.dataframe(pd.DataFrame(google_controls), use_container_width=True, hide_index=True)
                    control_labels = [
                        f"{item.get('text') or 'Google sign-in'} · {item.get('selector')}"
                        for item in google_controls
                    ]
                    chosen_control_label = st.selectbox(
                        "Detected Google sign-in button",
                        control_labels,
                        key="integrated_google_button_choice",
                    )
                    chosen_control = google_controls[control_labels.index(chosen_control_label)]
                    st.caption(
                        "SIMURU akan membuka halaman dan mengeklik tombol Google. "
                        "Kamu tetap menyelesaikan pemilihan Google Account, login, consent, CAPTCHA, dan MFA."
                    )
                    if st.button(
                        "Start Google OAuth registration",
                        type="primary",
                        use_container_width=True,
                        key="start_google_oauth_registration",
                    ):
                        try:
                            message = cpanel_manager.start_google_oauth_flow(
                                str(st.session_state["integrated_oauth_target"]),
                                str(chosen_control.get("selector", "")),
                            )
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "success",
                                "message": (
                                    message + " Test identity yang dipilih: "
                                    + str(st.session_state.get("integrated_oauth_email", ""))
                                ),
                            }
                        except MailboxError as exc:
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "error",
                                "message": str(exc),
                            }
                else:
                    st.warning(
                        "Tombol Google OAuth belum terdeteksi. Periksa URL halaman registrasi "
                        "dan pastikan tombol tersedia setelah halaman dimuat."
                    )
                    if st.button("Open registration page manually"):
                        try:
                            message = cpanel_manager.open_website_for_oauth_qa(
                                str(st.session_state["integrated_oauth_target"])
                            )
                            st.info(message)
                        except MailboxError as exc:
                            st.error(str(exc))
                st.caption(
                    "Ulangi satu per satu untuk setiap test identity. Pastikan akun Google sudah "
                    "terdaftar; mailbox saja belum cukup untuk login Google."
                )
    render_mailbox_workflow()

with website_tab:
    st.subheader("Website Automation · Visual Configuration")
    st.write(
        "Buat profil website melalui form. Konfigurasi disimpan lokal sebagai JSON; "
        "kamu tidak perlu mengedit file konfigurasi secara manual."
    )
    st.info(
        "Profil ini menyiapkan konfigurasi QA. Jalankan browser automation hanya pada "
        "website yang kamu miliki atau yang secara eksplisit mengizinkan pengujian."
    )
    profile_store = WebsiteProfileStore()
    try:
        saved_profiles = profile_store.list_profiles()
        saved_names = [str(item["name"]) for item in saved_profiles]
        selected_profile_name = st.selectbox(
            "Saved website profiles",
            ["— New website profile —", *saved_names],
            key="website_profile_selection",
        )
        selected_profile = next(
            (item for item in saved_profiles if item.get("name") == selected_profile_name),
            {},
        )
        selected_selectors = selected_profile.get("selectors", {})
        if not isinstance(selected_selectors, dict):
            selected_selectors = {}
        for field in ("name", "email", "password", "confirm_password", "submit"):
            st.session_state.setdefault(
                f"website_selector_{field}", str(selected_selectors.get(field, ""))
            )

        st.markdown("**Automatic form inspection**")
        inspect_url = st.text_input(
            "Registration page URL to inspect",
            value=(
                f"{str(selected_profile.get('base_url', '')).rstrip('/')}"
                f"{selected_profile.get('register_path', '/register')}"
                if selected_profile else ""
            ),
            placeholder="https://your-staging-site.com/register",
            key="website_inspect_url",
        )
        if st.button("Inspect Website & Auto-detect Selectors", type="secondary"):
            try:
                with st.spinner("Playwright is inspecting visible form fields..."):
                    inspection = inspect_form(inspect_url)
                st.session_state["website_inspection_result"] = inspection
                for field, selector in inspection["selectors"].items():
                    st.session_state[f"website_selector_{field}"] = selector
                st.success(
                    f"Inspected: {inspection['title'] or inspection['url']} · "
                    f"{len(inspection['inputs'])} input fields detected."
                )
                st.rerun()
            except FormInspectionError as exc:
                st.error(str(exc))

        inspection_result = st.session_state.get("website_inspection_result")
        if inspection_result:
            st.caption("Detected fields — review the suggested selectors before saving.")
            detected_rows = [
                {
                    "Label": item.get("label", ""),
                    "Type": item.get("type", ""),
                    "Name": item.get("name", ""),
                    "Suggested selector": item.get("selector", ""),
                }
                for item in inspection_result.get("inputs", [])
            ]
            if detected_rows:
                st.dataframe(pd.DataFrame(detected_rows), use_container_width=True, hide_index=True)
            google_buttons = inspection_result.get("google_buttons", [])
            if google_buttons:
                st.success("Google sign-in control detected:")
                st.dataframe(pd.DataFrame(google_buttons), use_container_width=True, hide_index=True)
            else:
                st.info("No obvious Google sign-in button was detected on this page.")

        with st.form("website_profile_visual_form"):
            st.markdown("**Website details**")
            p1, p2 = st.columns(2)
            with p1:
                website_name = st.text_input(
                    "Website name",
                    value=str(selected_profile.get("name", "")),
                    placeholder="My staging app",
                )
                base_url = st.text_input(
                    "Base URL",
                    value=str(selected_profile.get("base_url", "")),
                    placeholder="https://staging.example.com",
                )
            with p2:
                register_path = st.text_input(
                    "Registration path",
                    value=str(selected_profile.get("register_path", "/register")),
                    placeholder="/register",
                )
                auth_options = {
                    "Email + password": "email_password",
                    "Google OAuth": "google_oauth",
                    "Email + Google OAuth": "email_and_google",
                }
                current_auth = str(selected_profile.get("auth_method", "email_password"))
                auth_labels = list(auth_options)
                auth_index = list(auth_options.values()).index(current_auth) if current_auth in auth_options.values() else 0
                auth_label = st.selectbox(
                    "Authentication method",
                    auth_labels,
                    index=auth_index,
                )
            st.markdown("**Form selectors (CSS)**")
            s1, s2 = st.columns(2)
            with s1:
                selector_name = st.text_input("Name field selector", key="website_selector_name", placeholder="Auto-detected")
                selector_email = st.text_input("Email field selector", key="website_selector_email", placeholder="Auto-detected")
                selector_password = st.text_input("Password field selector", key="website_selector_password", placeholder="Auto-detected")
            with s2:
                selector_confirm = st.text_input("Confirm password selector", key="website_selector_confirm_password", placeholder="Auto-detected")
                selector_submit = st.text_input("Submit button selector", key="website_selector_submit", placeholder="Auto-detected")
                google_oauth_enabled = st.checkbox(
                    "Enable Google OAuth flow testing",
                    value=bool(selected_profile.get("google_oauth_enabled", False)),
                )
            authorized = st.checkbox(
                "I own this website or have explicit permission to run automated QA against it.",
                value=bool(selected_profile.get("authorized_for_testing", False)),
            )
            save_profile = st.form_submit_button("Save website profile", type="primary", use_container_width=True)

        if save_profile:
            try:
                profile_store.save({
                    "name": website_name,
                    "base_url": base_url,
                    "register_path": register_path,
                    "auth_method": auth_options[auth_label],
                    "google_oauth_enabled": google_oauth_enabled,
                    "selectors": {
                        "name": selector_name,
                        "email": selector_email,
                        "password": selector_password,
                        "confirm_password": selector_confirm,
                        "submit": selector_submit,
                    },
                    "authorized_for_testing": authorized,
                })
                st.success(f"Website profile '{website_name.strip()}' saved locally.")
                st.rerun()
            except WebsiteProfileError as exc:
                st.error(str(exc))

        if selected_profile:
            st.divider()
            st.markdown("**Selected profile preview**")
            st.code(profile_registration_url(selected_profile), language="text")
            st.json(selected_profile)
            if not selected_profile.get("authorized_for_testing"):
                st.warning("QA execution remains disabled until ownership/permission is confirmed.")
            if st.button("Delete selected profile", type="secondary"):
                profile_store.delete(selected_profile_name)
                st.success("Profile deleted.")
                st.rerun()
        elif not saved_profiles:
            st.caption("Belum ada profil. Isi form untuk menambahkan website pertama.")
    except WebsiteProfileError as exc:
        st.error(str(exc))

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
