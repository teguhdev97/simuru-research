from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import ImapOTPReader, MailboxError, MailboxSettings
from simuru_research.security.mailbox_vault import MailboxCredentialVault
from simuru_research.ui.email_multi_select import email_multi_select


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
            mailbox_for_otp = email_multi_select(
                "Mailbox untuk menerima OTP",
                [str(row["email"]) for row in mailbox_rows],
                key="otp_mailbox_selected",
                placeholder="Ketik email untuk mencari mailbox...",
                help_text=(
                    "Pilih hasil autocomplete, tekan Tab atau koma untuk menambahkan "
                    "sebagai pilihan. Pilihan tampil sebagai chip."
                ),
                max_selections=5,
            )
            otp_sender_allowlist = os.getenv("QA_OTP_ALLOWED_SENDERS", "").strip()
            if not otp_sender_allowlist:
                st.warning(
                    "Atur QA_OTP_ALLOWED_SENDERS pada .env dengan "
                    "sender yang diharapkan pada lingkungan staging milikmu."
                )
            if st.button("Check IMAP connection", key="check_imap_connection"):
                if not mailbox_for_otp:
                    st.warning("Pilih setidaknya satu mailbox untuk memeriksa IMAP.")
                else:
                    mailbox_settings = _mailbox_settings(cpanel_manager, mailbox_rows)
                    checked = 0
                    failures: list[str] = []
                    for email in mailbox_for_otp:
                        try:
                            ImapOTPReader(mailbox_settings).check_connection(email)
                            checked += 1
                        except MailboxError as exc:
                            failures.append(f"{email}: {exc}")
                    if failures:
                        st.error(
                            f"IMAP berhasil untuk {checked}/{len(mailbox_for_otp)} "
                            "mailbox. Gagal: " + "; ".join(failures)
                        )
                    else:
                        st.success(
                            f"IMAP login dan INBOX berhasil diperiksa untuk "
                            f"{checked} mailbox."
                        )
            otp_timeout = st.number_input(
                "OTP wait timeout (seconds)",
                min_value=10,
                max_value=180,
                value=60,
                step=5,
            )
            if st.button("Wait for fresh verification code", key="wait_for_mailbox_otp"):
                if not mailbox_for_otp:
                    st.warning("Pilih setidaknya satu mailbox untuk menunggu OTP.")
                else:
                    mailbox_settings = _mailbox_settings(cpanel_manager, mailbox_rows)
                    since = datetime.now(UTC)
                    otp_results: dict[str, str] = {}
                    failures: list[str] = []
                    with st.spinner(
                        f"Menunggu OTP dari {len(mailbox_for_otp)} mailbox..."
                    ):
                        with ThreadPoolExecutor(
                            max_workers=len(mailbox_for_otp)
                        ) as executor:
                            futures = {
                                email: executor.submit(
                                    ImapOTPReader(mailbox_settings).wait_for_otp,
                                    email,
                                    since=since,
                                    timeout_seconds=int(otp_timeout),
                                )
                                for email in mailbox_for_otp
                            }
                            for email, future in futures.items():
                                try:
                                    otp_results[email] = future.result()
                                except MailboxError as exc:
                                    failures.append(f"{email}: {exc}")
                    st.session_state["last_mailbox_otps"] = otp_results
                    if failures:
                        st.warning(
                            f"OTP diterima dari {len(otp_results)}/"
                            f"{len(mailbox_for_otp)} mailbox. "
                            + "; ".join(failures)
                        )
                    elif otp_results:
                        st.success(
                            f"OTP baru diterima dari {len(otp_results)} mailbox."
                        )
            if st.session_state.get("last_mailbox_otps"):
                for email, otp in st.session_state["last_mailbox_otps"].items():
                    st.caption(email)
                    st.code(otp)
                if st.button("Clear displayed OTPs", key="clear_mailbox_otp"):
                    st.session_state.pop("last_mailbox_otps", None)
                    st.rerun()
        else:
            st.warning(
                "Password mailbox belum semuanya tersimpan di Windows Credential Manager. "
                "Import password dari CSV satu per satu sebelum IMAP dapat digunakan."
            )


def _mailbox_settings(
    cpanel_manager: CpanelBrowserMailboxManager,
    mailbox_rows: list[dict[str, str]],
) -> MailboxSettings:
    return replace(
        MailboxSettings.from_env(),
        domain=cpanel_manager.domain,
        prefix=cpanel_manager.prefix,
        mailbox_passwords={
            str(row["email"]).lower(): str(row.get("password", ""))
            for row in mailbox_rows
            if row.get("status") == "created"
        },
    )