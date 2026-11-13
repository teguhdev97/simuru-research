from __future__ import annotations

import os

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError
from simuru_research.ui.mailbox_workflow import render_mailbox_workflow


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
    def render_mailbox_workflow_fragment() -> None:
        render_mailbox_workflow(cpanel_manager, mailbox_password_input)

    render_mailbox_workflow_fragment()
