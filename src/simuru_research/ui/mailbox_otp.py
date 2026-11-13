from __future__ import annotations

import os

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import ImapOTPReader, MailboxError, MailboxSettings
from simuru_research.security.mailbox_vault import MailboxCredentialVault


def render_mailbox_otp(
    cpanel_manager: CpanelBrowserMailboxManager,
    mailbox_rows: list[dict[str, str]],
    batch_complete: bool,
) -> None:
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