from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError
from simuru_research.security.mailbox_vault import MailboxCredentialVault
from simuru_research.ui.pagination import render_paginated_dataframe


def render_mailbox_batch(
    cpanel_manager: CpanelBrowserMailboxManager,
    mailbox_password_input: str,
) -> tuple[list[dict[str, str]], bool]:
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
        render_paginated_dataframe(
            mailbox_frame[valid_cols],
            key="mailbox_batch_results_pagination",
            alt="Latest mailbox batch results",
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
                width="stretch",
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
    return mailbox_rows, batch_complete


def render_mailbox_credential_import(cpanel_manager: CpanelBrowserMailboxManager) -> None:
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