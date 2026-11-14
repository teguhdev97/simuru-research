from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256

import streamlit as st

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.imap_inbox import ImapInboxReader
from simuru_research.providers.mailbox import MailboxSettings
from simuru_research.security.mailbox_vault import MailboxCredentialVault
from simuru_research.ui.pagination import paginate_items, render_pagination

EMAILS_PER_PAGE = 6


def render_mailbox_inbox(cpanel_manager: CpanelBrowserMailboxManager) -> None:
    addresses = st.session_state.get("domain_email_addresses", [])
    refresh_available = (
        st.session_state.get("domain_email_refresh_available", False)
        or bool(addresses)
    )
    refresh_col, count_col = st.columns([1, 3], vertical_alignment="center")
    with refresh_col:
        if refresh_available:
            refresh_addresses = st.button(
                "Refresh email list",
                icon=":material/refresh:",
                key="refresh_domain_email_addresses",
            )
        else:
            if st.button(
                "Check cPanel session",
                icon=":material/verified_user:",
                key="check_domain_inbox_cpanel_session",
            ):
                status = cpanel_manager.session_status()
                if status.get("connected"):
                    st.session_state["domain_email_refresh_available"] = True
                    st.session_state.pop("cpanel_connection_requested", None)
                    st.toast("cPanel session verified. Refresh the email list manually.")
                    st.rerun()
                else:
                    st.warning(
                        status.get(
                            "message",
                            "cPanel session is not ready. Finish signing in, then check again.",
                        )
                    )
            st.caption("Refresh email list appears after cPanel session verification.")
            refresh_addresses = False
    if refresh_addresses:
        try:
            current_addresses = cpanel_manager.list_domain_email_addresses()
            addresses = _newest_created_first(
                current_addresses,
                st.session_state.get("latest_mailbox_batch", []),
            )
            st.session_state["domain_email_addresses"] = addresses
            st.session_state["domain_email_refresh_available"] = True
            st.session_state["domain_email_refresh_pending"] = False
            st.session_state.pop("imap_inbox_loaded", None)
            st.session_state.pop("imap_inbox_opened_message", None)
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    addresses = st.session_state.get("domain_email_addresses", [])
    with count_col:
        st.caption(f"{len(addresses)} email accounts")
    if not addresses:
        if st.session_state.get("cpanel_connection_requested"):
            st.info(
                "Finish signing in to cPanel, check the session, then refresh the list "
                "manually. The mailbox list is not polled in the background."
            )
        else:
            st.info(
                "Connect cPanel, check the session after signing in, then refresh the list "
                "manually. The mailbox list is not polled in the background."
            )
        return
    if st.session_state.get("domain_email_refresh_pending"):
        st.info("A mailbox flow completed. Refresh the list to show the new addresses.")

    st.session_state.setdefault("imap_inbox_selected_mailbox", addresses[0])
    if st.session_state["imap_inbox_selected_mailbox"] not in addresses:
        st.session_state["imap_inbox_selected_mailbox"] = addresses[0]
    selected_email = st.session_state["imap_inbox_selected_mailbox"]
    address_column, message_column, detail_column = st.columns(
        [2.4, 1.7, 3.1],
        gap="small",
    )
    with address_column:
        st.markdown("**List email**")
        page = st.session_state.get("domain_email_pagination_page", 1)
        if not isinstance(page, int):
            page = 1
        page_addresses, _, _ = paginate_items(addresses, page, EMAILS_PER_PAGE)
        with st.container(key="domain-email-list", border=True):
            with st.container(key="domain-email-list-rows", height=500):
                for email in page_addresses:
                    address_key = sha256(email.encode("utf-8")).hexdigest()[:12]
                    if st.button(
                        _email_button_label(email),
                        key=f"domain_email_{address_key}",
                        icon=":material/mail:",
                        type="primary" if email == selected_email else "secondary",
                        width="stretch",
                    ):
                        st.session_state["imap_inbox_selected_mailbox"] = email
                        st.session_state.pop("imap_inbox_loaded", None)
                        st.session_state.pop("imap_inbox_opened_message", None)
                        st.rerun()
                    if len(email) > 36:
                        with st.expander(
                            "Full address",
                            expanded=False,
                            key=f"domain_email_address_{address_key}",
                        ):
                            st.caption(email)
            render_pagination(
                total_items=len(addresses),
                page_size=EMAILS_PER_PAGE,
                key="domain_email_pagination",
            )

    credential_vault = MailboxCredentialVault()
    mailbox_settings = replace(
        MailboxSettings.from_env(),
        domain=cpanel_manager.domain,
        prefix=cpanel_manager.prefix,
        mailbox_passwords={},
    )
    env_password = mailbox_settings.mailbox_master_password.strip()
    try:
        stored_password = (
            credential_vault.get(selected_email) if not env_password else None
        )
    except RuntimeError as exc:
        st.error(str(exc))
        return
    password_key = _mailbox_password_key(selected_email)
    st.session_state.setdefault(
        password_key,
        env_password or stored_password or "",
    )
    default_password = env_password or stored_password or ""

    with message_column:
        st.markdown("**Inbox**")
        with st.container(height=610, border=True):
            st.caption(selected_email)
            loaded = st.session_state.get("imap_inbox_loaded")
            loaded_for_selected = bool(
                loaded and loaded.get("email") == selected_email
            )
            attempted_emails = st.session_state.setdefault(
                "imap_inbox_auto_attempted_emails",
                [],
            )

            if (
                default_password
                and not loaded_for_selected
                and selected_email not in attempted_emails
            ):
                attempted_emails.append(selected_email)
                try:
                    with st.spinner("Connecting to mailbox..."):
                        loaded = _load_inbox(cpanel_manager, selected_email)
                    st.session_state["imap_inbox_loaded"] = loaded
                    st.session_state.pop("imap_inbox_login_error", None)
                    st.session_state.pop("imap_inbox_opened_message", None)
                    loaded_for_selected = True
                except (RuntimeError, ValueError) as exc:
                    st.session_state["imap_inbox_login_error"] = str(exc)
                    st.session_state["imap_inbox_login_error_email"] = selected_email
                    loaded = None

            login_error = st.session_state.get("imap_inbox_login_error")
            if (
                login_error
                and st.session_state.get("imap_inbox_login_error_email")
                == selected_email
            ):
                st.error(login_error)

            with st.expander(
                "Mailbox login",
                expanded=not loaded_for_selected,
            ):
                with st.form(
                    f"domain_mailbox_login_form_{sha256(selected_email.encode()).hexdigest()[:12]}",
                    clear_on_submit=False,
                ):
                    password = st.text_input(
                        "Mailbox password",
                        type="password",
                        key=password_key,
                    )
                    connect_mailbox = st.form_submit_button(
                        "Connect / retry",
                        type="primary",
                        width="stretch",
                    )
                if connect_mailbox:
                    if not password:
                        st.warning(
                            "Set QA_MAILBOX_MASTER_PASSWORD or enter a temporary "
                            "mailbox password."
                        )
                    else:
                        try:
                            with st.spinner("Connecting to mailbox..."):
                                loaded = _load_inbox(
                                    cpanel_manager,
                                    selected_email,
                                    password_override=password,
                                )
                            st.session_state["imap_inbox_loaded"] = loaded
                            st.session_state.pop("imap_inbox_login_error", None)
                            st.session_state.pop("imap_inbox_login_error_email", None)
                            st.session_state.pop("imap_inbox_opened_message", None)
                            if selected_email not in attempted_emails:
                                attempted_emails.append(selected_email)
                            st.rerun()
                        except (RuntimeError, ValueError) as exc:
                            st.session_state["imap_inbox_login_error"] = str(exc)
                            st.session_state["imap_inbox_login_error_email"] = selected_email
                            st.error(str(exc))

            if not default_password and not loaded_for_selected:
                st.info(
                    "Set QA_MAILBOX_MASTER_PASSWORD or enter the mailbox password "
                    "above. The password is not saved by this page."
                )

            query = st.text_input(
                "Search messages",
                placeholder="Search subject or sender",
                key="imap_inbox_search",
            ).strip().casefold()
            refresh_inbox = st.button(
                "Refresh inbox" if loaded_for_selected else "Load inbox",
                icon=":material/refresh:",
                type="primary" if not loaded_for_selected else "secondary",
                width="stretch",
                key="imap_inbox_refresh",
            )
            if refresh_inbox:
                try:
                    with st.spinner("Loading inbox..."):
                        loaded = _load_inbox(
                            cpanel_manager,
                            selected_email,
                            password_override=st.session_state.get(password_key, ""),
                        )
                    st.session_state["imap_inbox_loaded"] = loaded
                    st.session_state.pop("imap_inbox_login_error", None)
                    st.session_state.pop("imap_inbox_login_error_email", None)
                    st.session_state.pop("imap_inbox_opened_message", None)
                    loaded_for_selected = True
                except (RuntimeError, ValueError) as exc:
                    st.session_state.pop("imap_inbox_loaded", None)
                    loaded_for_selected = False
                    st.session_state["imap_inbox_login_error"] = str(exc)
                    st.session_state["imap_inbox_login_error_email"] = selected_email
                    st.error(str(exc))

            loaded_messages = (
                loaded.get("messages", [])
                if loaded and loaded.get("email") == selected_email
                else []
            )
            if query:
                loaded_messages = [
                    message
                    for message in loaded_messages
                    if query
                    in " ".join(
                        (
                            message.get("subject", ""),
                            message.get("sender", ""),
                            message.get("date", ""),
                        )
                    ).casefold()
                ]
            st.caption(f"{len(loaded_messages)} messages")
            if not loaded_for_selected and not refresh_inbox:
                if login_error:
                    st.info(
                        "Use Mailbox login to retry with a different password, or "
                        "check QA_MAILBOX_MASTER_PASSWORD."
                    )
                else:
                    st.info(
                        "Click Load inbox when you are ready to fetch messages."
                    )
            elif not loaded_messages:
                st.info("No messages in this inbox.")
            for message in loaded_messages:
                if st.button(
                    _message_label(message),
                    key=(
                        "inbox_message_"
                        + sha256(
                            f"{selected_email}:{message['message_id']}".encode()
                        ).hexdigest()[:12]
                    ),
                    icon=":material/mark_email_unread:",
                    width="stretch",
                    type=(
                        "primary"
                        if st.session_state.get("imap_inbox_opened_message", {}).get(
                            "message_id"
                        )
                        == message["message_id"]
                        else "secondary"
                    ),
                ):
                    try:
                        opened_message = _inbox_reader(
                            cpanel_manager,
                            selected_email,
                            password_override=st.session_state.get(password_key, ""),
                        ).read_message(
                            selected_email,
                            message["message_id"],
                        )
                        st.session_state["imap_inbox_opened_message"] = {
                            **opened_message,
                            "email": selected_email,
                            "message_id": message["message_id"],
                        }
                        st.rerun()
                    except (RuntimeError, ValueError) as exc:
                        st.session_state.pop("imap_inbox_opened_message", None)
                        st.error(str(exc))

    with detail_column:
        st.markdown("**Message**")
        with st.container(height=610, border=True):
            opened = st.session_state.get("imap_inbox_opened_message")
            if opened and opened.get("email") == selected_email:
                st.subheader(opened["subject"], anchor=False)
                st.caption(f"From: {opened['sender']}")
                st.caption(f"To: {selected_email}  ·  {opened['date']}")
                st.divider()
                st.text_area(
                    "Message body",
                    value=opened["body"] or "(No plain-text message body.)",
                    height=470,
                    disabled=True,
                    key=f"imap_inbox_message_body_{opened['message_id']}",
                )
            elif not loaded_for_selected:
                st.info("Connect the mailbox to view its messages.")
            else:
                st.info("Select a message from the inbox to read it.")


def _newest_created_first(
    addresses: list[str],
    mailbox_batch: list[dict[str, str]] | list[str],
) -> list[str]:
    known_newest: list[str] = []
    for row in reversed(mailbox_batch):
        if isinstance(row, str):
            email = row
        elif row.get("status") == "created":
            email = row.get("email", "")
        else:
            continue
        if email in addresses and email not in known_newest:
            known_newest.append(email)
    return known_newest + [email for email in addresses if email not in known_newest]


def _message_label(message: dict[str, str]) -> str:
    return (
        f"{message.get('subject', '(no subject)')}\n"
        f"{message.get('sender', '')} · {message.get('date', '')}"
    )


def _email_button_label(email: str) -> str:
    max_length = 36
    return email if len(email) <= max_length else f"{email[: max_length - 3]}..."


def _mailbox_password_key(email: str) -> str:
    return f"imap_mailbox_password_{sha256(email.encode()).hexdigest()[:12]}"


def _load_inbox(
    cpanel_manager: CpanelBrowserMailboxManager,
    email: str,
    *,
    password_override: str | None = None,
) -> dict[str, object]:
    reader = _inbox_reader(
        cpanel_manager,
        email,
        password_override=password_override,
    )
    messages = reader.list_messages(email)
    return {
        "email": email,
        "messages": [asdict(message) for message in messages],
    }


def _inbox_reader(
    cpanel_manager: CpanelBrowserMailboxManager,
    email: str | None = None,
    *,
    password_override: str | None = None,
) -> ImapInboxReader:
    mailbox_passwords = (
        {email: password_override}
        if email and password_override
        else {}
    )
    settings = replace(
        MailboxSettings.from_env(),
        domain=cpanel_manager.domain,
        prefix=cpanel_manager.prefix,
        mailbox_passwords=mailbox_passwords,
    )
    return ImapInboxReader(settings, allow_non_qa_mailboxes=True)
