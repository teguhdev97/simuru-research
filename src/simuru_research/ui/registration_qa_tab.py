from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.storage.exporter import results_to_csv


def render_registration_qa_tab(repository, auth_qa_service) -> None:
    st.subheader("Local Registration + Email/SMS Verification + Login QA")
    st.write(
        "Jalankan workflow registrasi aplikasi internal milik tim. Setiap akun QA "
        "dibuat di SQLite lokal, menerima kode dari local test outbox, memverifikasi "
        "email dan SMS, lalu melakukan login dan memvalidasi session."
    )
    st.warning(
        "Ini adalah aplikasi QA lokal, bukan Instagram. Tidak ada request ke Instagram, "
        "SIMURU number rental, Temp-Mail, Temp-Number, atau layanan pendaftaran pihak ketiga. "
        "Gunakan hanya untuk menguji aplikasi yang dimiliki tim."
    )

    qa_user_count = auth_qa_service.count_users()
    q1, q2, q3 = st.columns(3)
    q1.metric("Local QA users stored", qa_user_count)
    q2.metric("Batch target", 40)
    q3.metric("Default workers", 3)

    qa_col1, qa_col2 = st.columns(2)
    with qa_col1:
        qa_total_jobs = st.number_input(
            "Registration test users",
            min_value=1,
            max_value=100,
            value=40,
            step=1,
            key="registration_qa_total_jobs",
        )
    with qa_col2:
        qa_workers = st.number_input(
            "Concurrent registration workers",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
            key="registration_qa_workers",
        )

    st.caption(
        "Test fixtures use reserved addresses at example.test and fictional "
        "555-0100..0199 phone numbers. Passwords are hashed; OTPs are cleared "
        "from the local outbox after verification."
    )
    st.markdown(
        "**Satu job menjalankan:** register → email OTP → SMS OTP → login → "
        "session validation."
    )

    if st.button(
        "Run registration QA batch",
        type="primary",
        use_container_width=True,
        key="run_registration_qa_batch",
    ):
        try:
            with st.spinner(
                f"Running {qa_total_jobs} local registration flows "
                f"with {qa_workers} workers..."
            ):
                qa_summary = LocalRegistrationQARunner(
                    repository,
                    auth_qa_service,
                ).run_batch(
                    total_jobs=int(qa_total_jobs),
                    max_workers=int(qa_workers),
                )
            st.success(
                f"QA run {qa_summary.run_id[:8]} completed: "
                f"{qa_summary.passed} passed · {qa_summary.failed} failed."
            )
            st.session_state["latest_registration_qa_run"] = qa_summary.run_id
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))

    latest_qa_run = st.session_state.get("latest_registration_qa_run")
    if latest_qa_run:
        qa_results = repository.list_results(latest_qa_run)
        if qa_results:
            passed = sum(row["status"] == "passed" for row in qa_results)
            failed = len(qa_results) - passed
            qa_m1, qa_m2, qa_m3 = st.columns(3)
            qa_m1.metric("Completed jobs", len(qa_results))
            qa_m2.metric("Passed", passed)
            qa_m3.metric("Failed", failed)
            st.dataframe(
                pd.DataFrame(qa_results),
                use_container_width=True,
                hide_index=True,
            )
            csv_data = results_to_csv(qa_results)
            st.download_button(
                "Download registration QA results",
                data=csv_data,
                file_name=f"simuru-registration-qa-{latest_qa_run[:8]}.csv",
                mime="text/csv",
            )

    with st.expander("Inspect local QA users"):
        local_users = auth_qa_service.list_users(limit=100)
        if local_users:
            user_frame = pd.DataFrame(local_users)
            user_frame["email_verified"] = user_frame["email_verified"].astype(bool)
            user_frame["phone_verified"] = user_frame["phone_verified"].astype(bool)
            st.dataframe(
                user_frame,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No local QA users have been created yet.")