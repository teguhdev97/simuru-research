from __future__ import annotations

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError
from simuru_research.ui.mailbox_workflow import render_mailbox_workflow


def create_cpanel_manager() -> CpanelBrowserMailboxManager:
    return CpanelBrowserMailboxManager(
        cpanel_url="https://juwana.iixcp.rumahweb.net:2083",
        domain="teguhharits.com",
        prefix="qa",
        quota_mb=50,
    )


def render_mailbox_tab(
    _settings,
    cpanel_manager: CpanelBrowserMailboxManager | None = None,
) -> None:
    st.title("Mailbox", icon=":material/mail:")
    st.caption("Kelola akun email domain dan baca pesan tanpa meninggalkan inbox.")
    if cpanel_manager is None:
        cpanel_manager = create_cpanel_manager()

    with st.container(horizontal=True):
        if st.button(
            "Connect cPanel",
            type="primary",
            icon=":material/link:",
            key="connect_cpanel",
        ):
            try:
                cpanel_manager.connect()
                st.session_state["cpanel_connection_requested"] = True
                st.toast("Browser cPanel dibuka. Selesaikan login di jendela tersebut.")
                st.rerun()
            except MailboxError as exc:
                st.error(str(exc))
        if st.button(
            "Close cPanel",
            icon=":material/close:",
            key="close_cpanel",
        ):
            logout = cpanel_manager.close()
            if logout["server_logout_confirmed"] == "true":
                st.toast(logout["message"])
            else:
                st.warning(logout["message"])

    render_mailbox_workflow(cpanel_manager, cpanel_manager.mailbox_password)
