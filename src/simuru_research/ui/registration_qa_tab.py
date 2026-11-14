from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.providers.mailbox import MailboxError
from simuru_research.storage.exporter import results_to_csv
from simuru_research.ui.pagination import render_paginated_dataframe

REGISTRATION_QA_USERS = 5
REGISTRATION_QA_WORKERS = 2


def render_registration_qa_tab(repository, auth_qa_service, cpanel_manager) -> None:
    st.subheader("Local Registration + Email/SMS Verification + Login QA")
    st.write(
        "Buat lima mailbox baru pada domain teguhharits.com, lalu uji alur "
        "registrasi lokal menggunakan alamat tersebut."
    )
    st.warning(
        "Mailbox sungguhan akan dibuat di cPanel. OTP email/SMS pada alur QA tetap "
        "disimulasikan secara lokal; tidak ada OTP yang dikirim ke mailbox atau nomor telepon."
    )

    qa_user_count = auth_qa_service.count_users()
    q1, q2, q3 = st.columns(3)
    q1.metric("Local QA users stored", qa_user_count)
    q2.metric("Registration test users", REGISTRATION_QA_USERS)
    q3.metric("Concurrent workers", REGISTRATION_QA_WORKERS)

    if not cpanel_manager.mailbox_password:
        st.error(
            "QA_MAILBOX_MASTER_PASSWORD belum tersedia. Atur variabel tersebut "
            "sebelum membuat mailbox agar password tidak dibuat acak atau disimpan."
        )

    check_col, connect_col = st.columns(2)
    with check_col:
        if st.button("Check cPanel session", key="registration_check_cpanel"):
            try:
                status = cpanel_manager.session_status()
                st.session_state["registration_cpanel_ready"] = bool(
                    status.get("connected")
                )
                if st.session_state["registration_cpanel_ready"]:
                    st.success("cPanel session is ready.")
                else:
                    st.warning(
                        status.get("message", "Sign in to cPanel before continuing.")
                    )
            except MailboxError as exc:
                st.session_state["registration_cpanel_ready"] = False
                st.error(str(exc))
    with connect_col:
        st.button(
            "Open mailbox management",
            key="registration_open_mailbox",
            on_click=_open_mailbox_management,
            width="stretch",
        )

    if st.button(
        "Create 5 mailboxes and run registration QA",
        type="primary",
        width="stretch",
        key="run_registration_qa_batch",
        disabled=(
            not st.session_state.get("registration_cpanel_ready", False)
            or not cpanel_manager.mailbox_password
        ),
    ):
        try:
            with st.spinner("Creating and verifying five cPanel mailboxes..."):
                mailbox_rows = cpanel_manager.create_five(save_credentials=False)
            safe_mailbox_rows = [
                {
                    key: value
                    for key, value in row.items()
                    if key in {"email", "status", "error"}
                }
                for row in mailbox_rows
            ]
            st.session_state["latest_registration_mailboxes"] = safe_mailbox_rows
            email_addresses = [
                row["email"]
                for row in mailbox_rows
                if row.get("status") == "created"
            ]
            if len(mailbox_rows) != REGISTRATION_QA_USERS or len(
                email_addresses
            ) != REGISTRATION_QA_USERS:
                st.error(
                    f"Hanya {len(email_addresses)}/{REGISTRATION_QA_USERS} mailbox "
                    "yang berhasil diverifikasi. QA lokal tidak dijalankan."
                )
            else:
                st.session_state["domain_email_refresh_available"] = True
                st.session_state["domain_email_refresh_pending"] = True
                with st.spinner(
                    f"Running local registration QA with "
                    f"{REGISTRATION_QA_WORKERS} workers..."
                ):
                    qa_summary = LocalRegistrationQARunner(
                        repository,
                        auth_qa_service,
                    ).run_batch(
                        total_jobs=REGISTRATION_QA_USERS,
                        max_workers=REGISTRATION_QA_WORKERS,
                        email_addresses=email_addresses,
                    )
                st.success(
                    f"Created {len(email_addresses)} domain mailboxes. "
                    f"QA run {qa_summary.run_id[:8]}: "
                    f"{qa_summary.passed} passed · {qa_summary.failed} failed."
                )
                st.session_state["latest_registration_qa_run"] = qa_summary.run_id
        except (MailboxError, ValueError, RuntimeError) as exc:
            st.error(str(exc))

    mailbox_rows = st.session_state.get("latest_registration_mailboxes", [])
    if mailbox_rows:
        render_paginated_dataframe(
            pd.DataFrame(mailbox_rows),
            key="registration_mailboxes_pagination",
            alt="New cPanel mailbox creation results",
        )

    latest_qa_run = st.session_state.get("latest_registration_qa_run")
    if not latest_qa_run:
        latest_qa_run = _latest_domain_qa_run(
            repository,
            auth_qa_service.email_domain,
        )
    if latest_qa_run:
        qa_results = repository.list_results(latest_qa_run)
        if qa_results:
            passed = sum(row["status"] == "passed" for row in qa_results)
            failed = len(qa_results) - passed
            qa_m1, qa_m2, qa_m3 = st.columns(3)
            qa_m1.metric("Completed jobs", len(qa_results))
            qa_m2.metric("Passed", passed)
            qa_m3.metric("Failed", failed)
            render_paginated_dataframe(
                pd.DataFrame(qa_results),
                key="registration_qa_results_pagination",
                alt="Registration QA results",
            )
            csv_data = results_to_csv(qa_results)
            st.download_button(
                "Download registration QA results",
                data=csv_data,
                file_name=f"simuru-registration-qa-{latest_qa_run[:8]}.csv",
                mime="text/csv",
            )


def _open_mailbox_management() -> None:
    st.session_state["current_page"] = "Mailbox"
    st.session_state["mailbox_workspace"] = "Mailbox management"


def _latest_domain_qa_run(repository, email_domain: str) -> str | None:
    suffix = "@" + email_domain.lower()
    for run in repository.list_runs(limit=50):
        run_id = str(run["run_id"])
        results = repository.list_results(run_id)
        if results and all(
            str(result["email"]).lower().endswith(suffix)
            for result in results
        ):
            return run_id
    return None
