from __future__ import annotations

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError


def render_cpanel_status(cpanel_manager: CpanelBrowserMailboxManager) -> bool:
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
    return session_ready


def render_existing_mailboxes(
    cpanel_manager: CpanelBrowserMailboxManager,
    mailbox_password_input: str,
    session_ready: bool,
) -> None:
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

def render_mailbox_creation(
    cpanel_manager: CpanelBrowserMailboxManager,
    session_ready: bool,
) -> None:
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

def render_mailbox_alert() -> None:
    alert = st.session_state.get("mailbox_workflow_alert")
    if alert:
        if alert.get("kind") == "error":
            st.error(alert.get("message", "Mailbox operation failed."))
        elif alert.get("kind") == "success":
            st.success(alert.get("message", "Mailbox operation completed."))
        if st.button("Dismiss alert", key="dismiss_mailbox_workflow_alert"):
            st.session_state.pop("mailbox_workflow_alert", None)
            st.rerun()