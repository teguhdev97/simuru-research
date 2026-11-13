from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.engine.form_inspector import FormInspectionError, inspect_form
from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError


def render_owned_website_qa(
    cpanel_manager: CpanelBrowserMailboxManager,
    mailbox_rows: list[dict[str, str]],
    batch_complete: bool,
) -> None:
    if batch_complete:
        st.divider()
        st.subheader("Owned Website Registration QA")
        st.success("Lima mailbox berhasil dibuat dan diverifikasi.")
        test_emails = [str(row["email"]) for row in mailbox_rows]
        st.caption(
            "Jalur Google membutuhkan Google Accounts yang sudah ditambahkan ke "
            "OAuth Test Users. Jalur fallback email tidak membutuhkan Google Account."
        )
        st.code("\n".join(test_emails), language="text")
        with st.form("integrated_google_oauth_qa_form"):
            target_url = st.text_input(
                "Website registration URL",
                placeholder="https://your-staging-site.example/register",
            )
            selected_test_email = st.selectbox(
                "Google test account (OAuth only)",
                test_emails,
            )
            owns_target = st.checkbox(
                "Saya memiliki website ini atau memiliki izin "
                "eksplisit untuk menjalankan QA."
            )
            accounts_ready = st.checkbox(
                "Kelima alamat sudah menjadi Google Account dan "
                "ditambahkan ke OAuth Test Users (OAuth only)."
            )
            inspect_and_save = st.form_submit_button(
                "Inspect website & prepare registration QA",
                type="primary",
                use_container_width=True,
            )
        if inspect_and_save:
            if not owns_target:
                st.error("Konfirmasi kepemilikan/izin website sebelum menjalankan QA.")
            else:
                spinner_text = (
                    "Memeriksa halaman registrasi "
                    "dan tombol Google OAuth/email..."
                )
                try:
                    with st.spinner(spinner_text):
                        inspection = inspect_form(target_url)
                    st.session_state["integrated_oauth_target"] = target_url
                    st.session_state["integrated_oauth_inspection"] = inspection
                    st.session_state["integrated_oauth_email"] = selected_test_email
                    st.session_state["integrated_oauth_authorized"] = True
                    st.session_state["integrated_oauth_accounts_ready"] = accounts_ready
                    st.session_state.pop("email_fallback_results", None)
                    for field, selector in inspection.get("selectors", {}).items():
                        st.session_state[f"integrated_email_selector_{field}"] = selector
                    page_title_val = inspection.get("title") or inspection.get("url")
                    google_count = len(inspection.get("google_buttons", []))
                    st.success(
                        f"Halaman diperiksa: {page_title_val}. "
                        f"{google_count} kontrol Google terdeteksi."
                    )
                except FormInspectionError as exc:
                    st.error(str(exc))
        oauth_inspection = st.session_state.get("integrated_oauth_inspection")
        if oauth_inspection:
            google_controls = oauth_inspection.get("google_buttons", [])
            selector_labels = {
                "name": "Name field selector",
                "email": "Email field selector",
                "password": "Password field selector",
                "confirm_password": "Confirm password selector (optional)",
                "submit": "Submit button selector",
            }
            with st.expander(
                "Review email registration form selectors",
                expanded=not bool(google_controls),
            ):
                for field, label in selector_labels.items():
                    key = f"integrated_email_selector_{field}"
                    default_sel = str(oauth_inspection.get("selectors", {}).get(field, ""))
                    st.session_state.setdefault(key, default_sel)
                    st.text_input(
                        label,
                        key=key,
                        placeholder="Auto-detected CSS selector",
                    )

            def run_email_registration_fallback():
                if not st.session_state.get("integrated_oauth_authorized", False):
                    st.error(
                        "Konfirmasi kepemilikan website diperlukan sebelum email fallback."
                    )
                    return
                selectors = {
                    field: st.session_state.get(
                        f"integrated_email_selector_{field}", ""
                    )
                    for field in selector_labels
                }
                required = ("email", "password", "submit")
                missing = [
                    field for field in required
                    if not str(selectors.get(field, "")).strip()
                ]
                if missing:
                    missing_str = ", ".join(missing)
                    st.error(
                        "Form email belum bisa dijalankan. Selector belum terdeteksi: "
                        + missing_str
                        + ". Periksa atau koreksi selector pada panel di atas."
                    )
                    return

                identities = [
                    {
                        "email": str(row["email"]),
                        "password": cpanel_manager._generate_mailbox_password(),
                        "name": f"SIMURU QA User {index:02d}",
                    }
                    for index, row in enumerate(mailbox_rows, start=1)
                ]
                try:
                    spin_msg = (
                        "Menjalankan pendaftaran email secara berurutan "
                        "untuk 5 identitas QA..."
                    )
                    with st.spinner(spin_msg):
                        target_val = str(st.session_state["integrated_oauth_target"])
                        results = cpanel_manager.run_email_registration_batch(
                            target_val,
                            selectors,
                            identities,
                        )
                    st.session_state["email_fallback_results"] = results
                    submitted = sum(
                        item.get("status") == "submitted" for item in results
                    )
                    st.success(
                        f"Fallback email selesai: {submitted}/5 form berhasil dikirim. "
                        "Status submitted belum otomatis berarti email sudah terverifikasi."
                    )
                except MailboxError as exc:
                    st.error(f"Email fallback gagal: {exc}")

            if google_controls:
                st.dataframe(
                    pd.DataFrame(google_controls),
                    use_container_width=True,
                    hide_index=True,
                )
                control_labels = [
                    f"{item.get('text') or 'Google sign-in'} · {item.get('selector')}"
                    for item in google_controls
                ]
                chosen_control_label = st.selectbox(
                    "Detected Google sign-in button",
                    control_labels,
                    key="integrated_google_button_choice",
                )
                chosen_control = google_controls[
                    control_labels.index(chosen_control_label)
                ]
                st.caption(
                    "SIMURU akan membuka halaman dan mengeklik tombol Google. "
                    "Kamu tetap menyelesaikan pemilihan Google Account, login, consent, "
                    "CAPTCHA, dan MFA."
                )
                oauth_ready = st.session_state.get(
                    "integrated_oauth_accounts_ready",
                    False,
                )
                button_label = (
                    "Start Google OAuth registration"
                    if oauth_ready
                    else "Start email registration fallback (5)"
                )
                if st.button(
                    button_label,
                    type="primary",
                    use_container_width=True,
                    key="start_google_oauth_registration",
                ):
                    if not oauth_ready:
                        st.warning(
                            "Google Account belum disiapkan untuk OAuth. "
                            "SIMURU beralih ke pendaftaran email."
                        )
                        run_email_registration_fallback()
                    else:
                        try:
                            target_val = str(st.session_state["integrated_oauth_target"])
                            selector_val = str(chosen_control.get("selector", ""))
                            message = cpanel_manager.start_google_oauth_flow(
                                target_val,
                                selector_val,
                            )
                            email_val = str(
                                st.session_state.get(
                                    "integrated_oauth_email", ""
                                )
                            )
                            st.session_state["mailbox_workflow_alert"] = {
                                "kind": "success",
                                "message": (
                                    message + " Test identity yang dipilih: "
                                    + email_val
                                ),
                            }
                        except MailboxError as exc:
                            st.warning(
                                f"Tombol Google gagal dijalankan ({exc}). "
                                "SIMURU beralih ke fallback pendaftaran email."
                            )
                            run_email_registration_fallback()
            else:
                st.warning(
                    "Tombol Google OAuth tidak terdeteksi. SIMURU dapat memakai "
                    "form email/password yang terdeteksi untuk lima identitas QA."
                )
                fallback_disabled = bool(
                    st.session_state.get("email_fallback_results")
                )
                if st.button(
                    "Fallback: register 5 accounts with email",
                    type="primary",
                    use_container_width=True,
                    key="start_email_registration_fallback",
                    disabled=fallback_disabled,
                ):
                    run_email_registration_fallback()

            fallback_results = st.session_state.get("email_fallback_results", [])
            if fallback_results:
                visible_results = [
                    {
                        "email": item.get("email", ""),
                        "status": item.get("status", ""),
                        "message": item.get("message", ""),
                        "page_url": item.get("page_url", ""),
                    }
                    for item in fallback_results
                ]
                st.dataframe(
                    pd.DataFrame(visible_results),
                    use_container_width=True,
                    hide_index=True,
                )
                fallback_csv = (
                    pd.DataFrame(fallback_results)
                    .to_csv(index=False)
                    .encode("utf-8")
                )
                st.download_button(
                    "Download email QA credentials & results (CSV)",
                    data=fallback_csv,
                    file_name="simuru-email-registration-qa.csv",
                    mime="text/csv",
                    key="download_email_fallback_results",
                )
                if st.button(
                    "Clear email fallback results (allow rerun)",
                    key="clear_email_fallback_results",
                ):
                    st.session_state.pop("email_fallback_results", None)
                    st.rerun()
            st.caption(
                "Ulangi satu per satu untuk setiap test identity. "
                "Pastikan akun Google sudah terdaftar; "
                "mailbox saja belum cukup untuk login Google."
            )