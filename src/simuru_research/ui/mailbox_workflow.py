from __future__ import annotations

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.ui.mailbox_batch import render_mailbox_batch, render_mailbox_credential_import
from simuru_research.ui.mailbox_inbox import render_mailbox_inbox
from simuru_research.ui.mailbox_otp import render_mailbox_otp
from simuru_research.ui.mailbox_session import (
    render_cpanel_status,
    render_existing_mailboxes,
    render_mailbox_alert,
    render_mailbox_creation,
)


def render_mailbox_workflow(
    cpanel_manager: CpanelBrowserMailboxManager, mailbox_password_input: str
) -> None:
    st.session_state.setdefault("mailbox_workspace", "Domain inbox")
    workspace = st.segmented_control(
        "Mailbox workspace",
        options=["Domain inbox", "Mailbox management"],
        key="mailbox_workspace",
    )
    if workspace == "Domain inbox":
        render_mailbox_inbox(cpanel_manager)
        return

    session_ready = render_cpanel_status(cpanel_manager)
    mailbox_password_input = st.text_input(
        "Password for new QA mailboxes (optional)",
        value=mailbox_password_input,
        type="password",
        placeholder="Leave empty to generate unique passwords",
        help="Used only for the QA mailbox creation and reset tools below.",
        key="qa_mailbox_password_input",
    ).strip()
    cpanel_manager.mailbox_password = mailbox_password_input

    render_existing_mailboxes(cpanel_manager, mailbox_password_input, session_ready)
    render_mailbox_creation(cpanel_manager, session_ready)
    render_mailbox_alert()
    mailbox_rows, batch_complete = render_mailbox_batch(
        cpanel_manager, mailbox_password_input
    )
    render_mailbox_credential_import(cpanel_manager)
    if batch_complete:
        with st.expander("Advanced mailbox diagnostics", expanded=False):
            render_mailbox_otp(cpanel_manager, mailbox_rows, batch_complete)
