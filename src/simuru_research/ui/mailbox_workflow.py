from __future__ import annotations

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.ui.mailbox_batch import render_mailbox_batch, render_mailbox_credential_import
from simuru_research.ui.mailbox_otp import render_mailbox_otp
from simuru_research.ui.mailbox_registration_qa import render_owned_website_qa
from simuru_research.ui.mailbox_session import (
    render_cpanel_status,
    render_existing_mailboxes,
    render_mailbox_alert,
    render_mailbox_creation,
)


def render_mailbox_workflow(
    cpanel_manager: CpanelBrowserMailboxManager, mailbox_password_input: str
) -> None:
    session_ready = render_cpanel_status(cpanel_manager)
    render_existing_mailboxes(cpanel_manager, mailbox_password_input, session_ready)
    render_mailbox_creation(cpanel_manager, session_ready)
    render_mailbox_alert()
    mailbox_rows, batch_complete = render_mailbox_batch(
        cpanel_manager, mailbox_password_input
    )
    render_mailbox_credential_import(cpanel_manager)
    if batch_complete:
        render_mailbox_otp(cpanel_manager, mailbox_rows, batch_complete)
        render_owned_website_qa(cpanel_manager, mailbox_rows, batch_complete)
