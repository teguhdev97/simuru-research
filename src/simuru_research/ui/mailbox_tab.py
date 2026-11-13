from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from simuru_research.engine.form_inspector import (
    FormInspectionError,
    inspect_form,
)
from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import (
    ImapOTPReader,
    MailboxError,
    MailboxSettings,
)
from simuru_research.security.mailbox_vault import MailboxCredentialVault


def render_mailbox_tab(_settings) -> None:
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
            "Field ini hanya berada di sesi dashboard; "
            ".env lokal lebih cocok untuk konfigurasi tetap."
        ),
        key="qa_mailbox_password_input",
    ).strip()
    notice_dismissed = st.session_state.get(
        "mailbox_password_notice_dismissed",
        False,
    )
    if not mailbox_password_input and not notice_dismissed:
        with st.container(border=True):
            notice_col, dismiss_col = st.columns([8, 1])
            with notice_col:
                st.warning(
                    "Password seragam belum diatur. Pembuatan tetap bisa "
                    "berjalan dengan password acak dan unik untuk setiap mailbox; "
                    "kredensial tersedia melalui CSV."
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
        refresh_btn = st.button(
            "Refresh existing mailbox list",
            key="refresh_existing_mailboxes",
        )
        if refresh_btn:
            try:
                mailboxes = cpanel_manager.list_domain_mailboxes()
                st.session_state["existing_qa_mailboxes"] = mailboxes
                st.session_state["mailbox_workflow_alert"] = {
                    "kind": "success",
                    "message": (
                        f"Ditemukan {len(mailboxes)} mailbox "
                        f"dengan prefix {cpanel_manager.prefix} "
                        f"pada domain {cpanel_manager.domain}."
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
                        with st.spinner(
                            "Memperbarui password mailbox terpilih..."
                        ):
                            reset_rows = cpanel_manager.reset_mailbox_passwords(
                                selected_existing_mailboxes
                            )
                        all_updated = all(
                            row["status"] == "updated" for row in reset_rows
                        )
                        if reset_rows and all_updated:
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "success",
                                "message": (
                                    f"Password berhasil diperbarui untuk "
                                    f"{len(reset_rows)} mailbox. "
                                    "Simpan password ini dengan aman."
                                ),
                            }
                        else:
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "error",
                                "message": (
                                    "Sebagian mailbox gagal diubah: "
                                    + str(reset_rows)
                                ),
                            }
                    except MailboxError as exc:
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "error",
                            "message": str(exc),
                        }
        elif session_ready:
            st.caption(
                "Klik Refresh existing mailbox list untuk memuat "
                "mailbox QA yang sudah ada."
            )

        create_btn = st.button(
            "Create 5 New Emails",
            type="primary",
            use_container_width=True,
            key="create_five_mailboxes",
            disabled=not session_ready,
        )
        if create_btn:
            st.session_state.pop("latest_mailbox_batch", None)
            try:
                with st.spinner(
                    "Membuat tepat lima mailbox dan memverifikasi hasilnya..."
                ):
                    mailbox_rows = cpanel_manager.create_five()
                st.session_state["latest_mailbox_batch"] = mailbox_rows
                successful = sum(
                    row.get("status") == "created" for row in mailbox_rows
                )
                if successful == 5 and len(mailbox_rows) == 5:
                    st.session_state["mailbox_workflow_alert"] = {
                        "kind": "success",
                        "message": (
                            "Berhasil membuat dan memverifikasi kelima mailbox."
                        ),
                    }
                else:
                    st.session_state["mailbox_workflow_alert"] = {
                        "kind": "error",
                        "message": (
                            f"Baru {successful}/5 mailbox terverifikasi. "
                            "Tahap Google OAuth belum dibuka. "
                            "Periksa tabel hasil."
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
            email_val = str(mailbox_row["email"])
            if (
                mailbox_row.get("status") == "created"
                and MailboxCredentialVault().get(email_val)
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
            valid_cols = [
                col for col in ["email", "status", "credential_storage", "error"]
                if col in mailbox_frame.columns
            ]
            st.dataframe(
                mailbox_frame[valid_cols],
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
                if st.button(
                    "Set same password for these 5 mailboxes",
                    use_container_width=True,
                ):
                    try:
                        with st.spinner("Memperbarui password mailbox di cPanel..."):
                            created_emails = [
                                str(row["email"]) for row in mailbox_rows
                                if row.get("status") == "created"
                            ]
                            reset_rows = cpanel_manager.reset_mailbox_passwords(
                                created_emails
                            )
                        st.session_state["mailbox_password_reset"] = reset_rows
                        all_updated = all(
                            row["status"] == "updated" for row in reset_rows
                        )
                        if reset_rows and all_updated:
                            for mailbox_row in mailbox_rows:
                                if mailbox_row.get("status") == "created":
                                    mailbox_row["password"] = mailbox_password_input
                            st.session_state["latest_mailbox_batch"] = mailbox_rows
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "success",
                                "message": (
                                    "Password mailbox berhasil diseragamkan. "
                                    "Download ulang CSV agar berisi password terbaru."
                                ),
                            }
                        else:
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "error",
                                "message": (
                                    "Sebagian password belum berhasil diperbarui: "
                                    + str(reset_rows)
                                ),
                            }
                    except MailboxError as exc:
                        st.session_state["mailbox_workflow_alert"] = {
                            "kind": "error",
                            "message": str(exc),
                        }
            else:
                st.info(
                    "Password acak unik sedang digunakan. "
                    "Isi field Shared QA mailbox password untuk "
                    "menyamakan password kelima mailbox."
                )

        with st.expander("Import existing mailbox password from CSV", expanded=False):
            st.caption(
                "Gunakan untuk mailbox yang telah dibuat sebelumnya. "
                "Password hanya disimpan di Windows Credential Manager lokal, "
                "bukan SQLite atau Git."
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
                        "message": (
                            "Mailbox password tersimpan di "
                            "Windows Credential Manager."
                        ),
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
                "IMAP dipakai untuk membaca OTP masuk. "
                "SMTP hanya dibutuhkan bila SIMURU perlu mengirim email."
            )
            imap_ready = all(
                MailboxCredentialVault().get(str(row["email"]))
                for row in mailbox_rows
            )
            if imap_ready:
                st.success(
                    "Kelima password mailbox tersedia di "
                    "Windows Credential Manager."
                )
                mailbox_for_otp = st.selectbox(
                    "Mailbox untuk menerima OTP",
                    [str(row["email"]) for row in mailbox_rows],
                    key="otp_mailbox_selected",
                )
                otp_sender_allowlist = os.getenv("QA_OTP_ALLOWED_SENDERS", "").strip()
                if not otp_sender_allowlist:
                    st.warning(
                        "Atur QA_OTP_ALLOWED_SENDERS pada .env dengan "
                        "sender yang diharapkan pada lingkungan staging milikmu."
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
                            "message": (
                                "IMAP login berhasil dan "
                                "folder INBOX dapat dibuka."
                            ),
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
                            "message": (
                                "Kode verifikasi baru berhasil "
                                "diterima dari mailbox."
                            ),
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
            st.subheader("Owned Website Registration QA")
            st.success("Lima mailbox berhasil dibuat dan diverifikasi.")
            test_emails = [str(row["email"]) for row in mailbox_rows]
            st.caption(
                "Jalur Google membutuhkan Google Accounts yang sudah ditambahkan ke "
                "OAuth Test Users. Jalur fallback email tidak membutuhkan Google Account."
            )
            st.code("\n".join(test_emails), language="text")
            with st.form("integrated_google_oauth_qa_form"):
                target_url = st.text_input(
                    "Website registration URL",
                    placeholder="https://your-staging-site.example/register",
                )
                selected_test_email = st.selectbox(
                    "Google test account (OAuth only)",
                    test_emails,
                )
                owns_target = st.checkbox(
                    "Saya memiliki website ini atau memiliki izin "
                    "eksplisit untuk menjalankan QA."
                )
                accounts_ready = st.checkbox(
                    "Kelima alamat sudah menjadi Google Account dan "
                    "ditambahkan ke OAuth Test Users (OAuth only)."
                )
                inspect_and_save = st.form_submit_button(
                    "Inspect website & prepare registration QA",
                    type="primary",
                    use_container_width=True,
                )
            if inspect_and_save:
                if not owns_target:
                    st.error("Konfirmasi kepemilikan/izin website sebelum menjalankan QA.")
                else:
                    spinner_text = (
                        "Memeriksa halaman registrasi "
                        "dan tombol Google OAuth/email..."
                    )
                    try:
                        with st.spinner(spinner_text):
                            inspection = inspect_form(target_url)
                        st.session_state["integrated_oauth_target"] = target_url
                        st.session_state["integrated_oauth_inspection"] = inspection
                        st.session_state["integrated_oauth_email"] = selected_test_email
                        st.session_state["integrated_oauth_authorized"] = True
                        st.session_state["integrated_oauth_accounts_ready"] = accounts_ready
                        st.session_state.pop("email_fallback_results", None)
                        for field, selector in inspection.get("selectors", {}).items():
                            st.session_state[f"integrated_email_selector_{field}"] = selector
                        page_title_val = inspection.get("title") or inspection.get("url")
                        google_count = len(inspection.get("google_buttons", []))
                        st.success(
                            f"Halaman diperiksa: {page_title_val}. "
                            f"{google_count} kontrol Google terdeteksi."
                        )
                    except FormInspectionError as exc:
                        st.error(str(exc))
            oauth_inspection = st.session_state.get("integrated_oauth_inspection")
            if oauth_inspection:
                google_controls = oauth_inspection.get("google_buttons", [])
                selector_labels = {
                    "name": "Name field selector",
                    "email": "Email field selector",
                    "password": "Password field selector",
                    "confirm_password": "Confirm password selector (optional)",
                    "submit": "Submit button selector",
                }
                with st.expander(
                    "Review email registration form selectors",
                    expanded=not bool(google_controls),
                ):
                    for field, label in selector_labels.items():
                        key = f"integrated_email_selector_{field}"
                        default_sel = str(oauth_inspection.get("selectors", {}).get(field, ""))
                        st.session_state.setdefault(key, default_sel)
                        st.text_input(
                            label,
                            key=key,
                            placeholder="Auto-detected CSS selector",
                        )

                def run_email_registration_fallback():
                    if not st.session_state.get("integrated_oauth_authorized", False):
                        st.error(
                            "Konfirmasi kepemilikan website diperlukan sebelum email fallback."
                        )
                        return
                    selectors = {
                        field: st.session_state.get(
                            f"integrated_email_selector_{field}", ""
                        )
                        for field in selector_labels
                    }
                    required = ("email", "password", "submit")
                    missing = [
                        field for field in required
                        if not str(selectors.get(field, "")).strip()
                    ]
                    if missing:
                        missing_str = ", ".join(missing)
                        st.error(
                            "Form email belum bisa dijalankan. Selector belum terdeteksi: "
                            + missing_str
                            + ". Periksa atau koreksi selector pada panel di atas."
                        )
                        return

                    identities = [
                        {
                            "email": str(row["email"]),
                            "password": cpanel_manager._generate_mailbox_password(),
                            "name": f"SIMURU QA User {index:02d}",
                        }
                        for index, row in enumerate(mailbox_rows, start=1)
                    ]
                    try:
                        spin_msg = (
                            "Menjalankan pendaftaran email secara berurutan "
                            "untuk 5 identitas QA..."
                        )
                        with st.spinner(spin_msg):
                            target_val = str(st.session_state["integrated_oauth_target"])
                            results = cpanel_manager.run_email_registration_batch(
                                target_val,
                                selectors,
                                identities,
                            )
                        st.session_state["email_fallback_results"] = results
                        submitted = sum(
                            item.get("status") == "submitted" for item in results
                        )
                        st.success(
                            f"Fallback email selesai: {submitted}/5 form berhasil dikirim. "
                            "Status submitted belum otomatis berarti email sudah terverifikasi."
                        )
                    except MailboxError as exc:
                        st.error(f"Email fallback gagal: {exc}")

                if google_controls:
                    st.dataframe(
                        pd.DataFrame(google_controls),
                        use_container_width=True,
                        hide_index=True,
                    )
                    control_labels = [
                        f"{item.get('text') or 'Google sign-in'} · {item.get('selector')}"
                        for item in google_controls
                    ]
                    chosen_control_label = st.selectbox(
                        "Detected Google sign-in button",
                        control_labels,
                        key="integrated_google_button_choice",
                    )
                    chosen_control = google_controls[
                        control_labels.index(chosen_control_label)
                    ]
                    st.caption(
                        "SIMURU akan membuka halaman dan mengeklik tombol Google. "
                        "Kamu tetap menyelesaikan pemilihan Google Account, login, consent, "
                        "CAPTCHA, dan MFA."
                    )
                    oauth_ready = st.session_state.get(
                        "integrated_oauth_accounts_ready",
                        False,
                    )
                    button_label = (
                        "Start Google OAuth registration"
                        if oauth_ready
                        else "Start email registration fallback (5)"
                    )
                    if st.button(
                        button_label,
                        type="primary",
                        use_container_width=True,
                        key="start_google_oauth_registration",
                    ):
                        if not oauth_ready:
                            st.warning(
                                "Google Account belum disiapkan untuk OAuth. "
                                "SIMURU beralih ke pendaftaran email."
                            )
                            run_email_registration_fallback()
                        else:
                            try:
                                target_val = str(st.session_state["integrated_oauth_target"])
                                selector_val = str(chosen_control.get("selector", ""))
                                message = cpanel_manager.start_google_oauth_flow(
                                    target_val,
                                    selector_val,
                                )
                                email_val = str(
                                    st.session_state.get(
                                        "integrated_oauth_email", ""
                                    )
                                )
                                st.session_state["mailbox_workflow_alert"] = {
                                    "kind": "success",
                                    "message": (
                                        message + " Test identity yang dipilih: "
                                        + email_val
                                    ),
                                }
                            except MailboxError as exc:
                                st.warning(
                                    f"Tombol Google gagal dijalankan ({exc}). "
                                    "SIMURU beralih ke fallback pendaftaran email."
                                )
                                run_email_registration_fallback()
                else:
                    st.warning(
                        "Tombol Google OAuth tidak terdeteksi. SIMURU dapat memakai "
                        "form email/password yang terdeteksi untuk lima identitas QA."
                    )
                    fallback_disabled = bool(
                        st.session_state.get("email_fallback_results")
                    )
                    if st.button(
                        "Fallback: register 5 accounts with email",
                        type="primary",
                        use_container_width=True,
                        key="start_email_registration_fallback",
                        disabled=fallback_disabled,
                    ):
                        run_email_registration_fallback()

                fallback_results = st.session_state.get("email_fallback_results", [])
                if fallback_results:
                    visible_results = [
                        {
                            "email": item.get("email", ""),
                            "status": item.get("status", ""),
                            "message": item.get("message", ""),
                            "page_url": item.get("page_url", ""),
                        }
                        for item in fallback_results
                    ]
                    st.dataframe(
                        pd.DataFrame(visible_results),
                        use_container_width=True,
                        hide_index=True,
                    )
                    fallback_csv = (
                        pd.DataFrame(fallback_results)
                        .to_csv(index=False)
                        .encode("utf-8")
                    )
                    st.download_button(
                        "Download email QA credentials & results (CSV)",
                        data=fallback_csv,
                        file_name="simuru-email-registration-qa.csv",
                        mime="text/csv",
                        key="download_email_fallback_results",
                    )
                    if st.button(
                        "Clear email fallback results (allow rerun)",
                        key="clear_email_fallback_results",
                    ):
                        st.session_state.pop("email_fallback_results", None)
                        st.rerun()
                st.caption(
                    "Ulangi satu per satu untuk setiap test identity. "
                    "Pastikan akun Google sudah terdaftar; "
                    "mailbox saja belum cukup untuk login Google."
                )
    render_mailbox_workflow()