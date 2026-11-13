from __future__ import annotations

import pandas as pd
import streamlit as st

from simuru_research.config.website_profiles import (
    WebsiteProfileError,
    WebsiteProfileStore,
    profile_registration_url,
)
from simuru_research.engine.form_inspector import (
    FormInspectionError,
    inspect_form,
)


def render_website_tab() -> None:
    st.subheader("Website Automation · Visual Configuration")
    st.write(
        "Buat profil website melalui form. Konfigurasi disimpan lokal sebagai JSON; "
        "kamu tidak perlu mengedit file konfigurasi secara manual."
    )
    st.info(
        "Profil ini menyiapkan konfigurasi QA. Jalankan browser automation hanya pada "
        "website yang kamu miliki atau yang secara eksplisit mengizinkan pengujian."
    )
    profile_store = WebsiteProfileStore()
    try:
        saved_profiles = profile_store.list_profiles()
        saved_names = [str(item["name"]) for item in saved_profiles]
        selected_profile_name = st.selectbox(
            "Saved website profiles",
            ["— New website profile —", *saved_names],
            key="website_profile_selection",
        )
        selected_profile = next(
            (item for item in saved_profiles if item.get("name") == selected_profile_name),
            {},
        )
        selected_selectors = selected_profile.get("selectors", {})
        if not isinstance(selected_selectors, dict):
            selected_selectors = {}
        for field in ("name", "email", "password", "confirm_password", "submit"):
            sel_val = str(selected_selectors.get(field, ""))
            st.session_state.setdefault(f"website_selector_{field}", sel_val)

        st.markdown("**Automatic form inspection**")
        base_url_val = str(selected_profile.get("base_url", "")).rstrip("/")
        reg_path_val = selected_profile.get("register_path", "/register")
        default_inspect = f"{base_url_val}{reg_path_val}" if selected_profile else ""
        inspect_url = st.text_input(
            "Registration page URL to inspect",
            value=default_inspect,
            placeholder="https://your-staging-site.com/register",
            key="website_inspect_url",
        )
        if st.button("Inspect Website & Auto-detect Selectors", type="secondary"):
            try:
                with st.spinner("Playwright is inspecting visible form fields..."):
                    inspection = inspect_form(inspect_url)
                st.session_state["website_inspection_result"] = inspection
                for field, selector in inspection["selectors"].items():
                    st.session_state[f"website_selector_{field}"] = selector
                page_title = inspection["title"] or inspection["url"]
                input_count = len(inspection["inputs"])
                st.success(
                    f"Inspected: {page_title} · {input_count} input fields detected."
                )
                st.rerun()
            except FormInspectionError as exc:
                st.error(str(exc))

        inspection_result = st.session_state.get("website_inspection_result")
        if inspection_result:
            st.caption("Detected fields — review the suggested selectors before saving.")
            detected_rows = [
                {
                    "Label": item.get("label", ""),
                    "Type": item.get("type", ""),
                    "Name": item.get("name", ""),
                    "Suggested selector": item.get("selector", ""),
                }
                for item in inspection_result.get("inputs", [])
            ]
            if detected_rows:
                st.dataframe(
                    pd.DataFrame(detected_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            google_buttons = inspection_result.get("google_buttons", [])
            if google_buttons:
                st.success("Google sign-in control detected:")
                st.dataframe(
                    pd.DataFrame(google_buttons),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No obvious Google sign-in button was detected on this page.")

        with st.form("website_profile_visual_form"):
            st.markdown("**Website details**")
            p1, p2 = st.columns(2)
            with p1:
                website_name = st.text_input(
                    "Website name",
                    value=str(selected_profile.get("name", "")),
                    placeholder="My staging app",
                )
                base_url = st.text_input(
                    "Base URL",
                    value=str(selected_profile.get("base_url", "")),
                    placeholder="https://staging.example.com",
                )
            with p2:
                register_path = st.text_input(
                    "Registration path",
                    value=str(selected_profile.get("register_path", "/register")),
                    placeholder="/register",
                )
                auth_options = {
                    "Email + password": "email_password",
                    "Google OAuth": "google_oauth",
                    "Email + Google OAuth": "email_and_google",
                }
                current_auth = str(selected_profile.get("auth_method", "email_password"))
                auth_labels = list(auth_options)
                auth_vals = list(auth_options.values())
                auth_index = auth_vals.index(current_auth) if current_auth in auth_vals else 0
                auth_label = st.selectbox(
                    "Authentication method",
                    auth_labels,
                    index=auth_index,
                )
            st.markdown("**Form selectors (CSS)**")
            s1, s2 = st.columns(2)
            with s1:
                selector_name = st.text_input(
                    "Name field selector",
                    key="website_selector_name",
                    placeholder="Auto-detected",
                )
                selector_email = st.text_input(
                    "Email field selector",
                    key="website_selector_email",
                    placeholder="Auto-detected",
                )
                selector_password = st.text_input(
                    "Password field selector",
                    key="website_selector_password",
                    placeholder="Auto-detected",
                )
            with s2:
                selector_confirm = st.text_input(
                    "Confirm password selector",
                    key="website_selector_confirm_password",
                    placeholder="Auto-detected",
                )
                selector_submit = st.text_input(
                    "Submit button selector",
                    key="website_selector_submit",
                    placeholder="Auto-detected",
                )
                google_oauth_enabled = st.checkbox(
                    "Enable Google OAuth flow testing",
                    value=bool(selected_profile.get("google_oauth_enabled", False)),
                )
            authorized = st.checkbox(
                "I own this website or have explicit "
                "permission to run automated QA against it.",
                value=bool(selected_profile.get("authorized_for_testing", False)),
            )
            save_profile = st.form_submit_button(
                "Save website profile",
                type="primary",
                use_container_width=True,
            )

        if save_profile:
            try:
                profile_store.save({
                    "name": website_name,
                    "base_url": base_url,
                    "register_path": register_path,
                    "auth_method": auth_options[auth_label],
                    "google_oauth_enabled": google_oauth_enabled,
                    "selectors": {
                        "name": selector_name,
                        "email": selector_email,
                        "password": selector_password,
                        "confirm_password": selector_confirm,
                        "submit": selector_submit,
                    },
                    "authorized_for_testing": authorized,
                })
                st.success(f"Website profile '{website_name.strip()}' saved locally.")
                st.rerun()
            except WebsiteProfileError as exc:
                st.error(str(exc))

        if selected_profile:
            st.divider()
            st.markdown("**Selected profile preview**")
            st.code(profile_registration_url(selected_profile), language="text")
            st.json(selected_profile)
            if not selected_profile.get("authorized_for_testing"):
                st.warning(
                    "QA execution remains disabled until ownership/permission is confirmed."
                )
            if st.button("Delete selected profile", type="secondary"):
                profile_store.delete(selected_profile_name)
                st.success("Profile deleted.")
                st.rerun()
        elif not saved_profiles:
            st.caption("Belum ada profil. Isi form untuk menambahkan website pertama.")
    except WebsiteProfileError as exc:
        st.error(str(exc))