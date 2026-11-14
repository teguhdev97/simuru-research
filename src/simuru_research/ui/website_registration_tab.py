from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from simuru_research.engine.website_registration_qa import (
    WebsiteRegistrationQAError,
    inspect_registration_form,
)
from simuru_research.storage.website_registration import WebsiteRegistrationRepository
from simuru_research.ui.pagination import render_paginated_dataframe


def render_website_registration_tab(database_path, auth_qa_service) -> None:
    repository = WebsiteRegistrationRepository(database_path)
    st.title("Website Registration", icon=":material/language:")
    st.caption("Inspect an authorized registration page and save a QA record.")

    with st.container(border=True):
        st.subheader("Authorized website QA")
        st.write(
            "This flow inspects visible form fields only. It does not submit forms, "
            "create accounts, or complete CAPTCHA and consent steps."
        )
        target_url = st.text_input(
            "Website registration URL",
            value="https://santrikoding.com/register",
            key="website_registration_target_url",
        )
        authorized = st.checkbox(
            "I own this domain or have written permission to test it.",
            key="website_registration_authorized",
        )
        if st.button(
            "Inspect website form",
            type="primary",
            icon=":material/search:",
            key="website_registration_inspect",
            width="stretch",
        ):
            if not authorized:
                st.error("Confirm authorization before inspecting this target.")
            else:
                try:
                    with st.spinner("Inspecting the registration form…"):
                        result = inspect_registration_form(target_url)
                    st.session_state["website_registration_inspection"] = result
                    st.session_state["website_registration_inspected_url"] = target_url
                    st.success(
                        f"Inspection complete: {len(result.get('inputs', []))} fields "
                        f"and {len(result.get('buttons', []))} buttons found."
                    )
                except (WebsiteRegistrationQAError, RuntimeError, ValueError) as exc:
                    st.error(f"Inspection failed: {exc}")

    inspection = st.session_state.get("website_registration_inspection")
    if inspection:
        with st.container(border=True):
            st.subheader("Detected registration form")
            a, b, c, d = st.columns(4)
            a.metric("Form", "Found" if inspection.get("formFound") else "Not found")
            b.metric("Fields", len(inspection.get("inputs", [])))
            c.metric("Buttons", len(inspection.get("buttons", [])))
            d.metric("Challenge", "Manual" if inspection.get("challengeDetected") else "None found")
            render_paginated_dataframe(
                pd.DataFrame(inspection.get("inputs", [])),
                key="website_registration_inputs",
                alt="Detected website registration fields",
            )
            st.caption("Selector suggestions are metadata for manual QA only.")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Field": name, "Selector": selector}
                        for name, selector in inspection.get("suggested_selectors", {}).items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            emails = [
                str(row["email"])
                for row in auth_qa_service.list_users(limit=500)
                if row.get("email")
            ]
            st.text_area(
                "QA email addresses (one per line)",
                value="\n".join(emails[:5]),
                key="website_registration_qa_emails",
            )
            if st.button("Save QA inspection record", key="save_website_qa_record"):
                clean_emails = sorted(
                    {
                        item.strip().lower()
                        for item in st.session_state[
                            "website_registration_qa_emails"
                        ].splitlines()
                        if item.strip()
                    }
                )
                if not clean_emails:
                    st.error("Add at least one QA email address.")
                else:
                    host = urlparse(
                        str(st.session_state["website_registration_inspected_url"])
                    ).hostname or ""
                    repository.create_run(
                        target_url=str(
                            st.session_state["website_registration_inspected_url"]
                        ),
                        website_host=host,
                        emails=clean_emails,
                    )
                    st.success("QA inspection record saved.")

    st.divider()
    with st.container(border=True):
        st.subheader("Website QA history")
        runs = repository.list_runs(limit=repository.count_runs() or 1)
        if runs:
            render_paginated_dataframe(
                pd.DataFrame(
                    [
                        {
                            "Website": row["website_host"],
                            "URL": row["target_url"],
                            "Status": row["status"],
                            "Created": row["created_at"],
                            "Run ID": row["run_id"][:8],
                        }
                        for row in runs
                    ]
                ),
                key="website_registration_history",
                alt="Website registration QA history",
            )
            selected = st.multiselect(
                "Open test registration details",
                [row["run_id"] for row in runs],
                default=[row["run_id"] for row in runs[:3]],
                format_func=lambda value: next(
                    f"{row['website_host']} · {row['run_id'][:8]}"
                    for row in runs
                    if row["run_id"] == value
                ),
                key="website_registration_detail_runs",
            )
            for run_id in selected:
                detail = repository.get_run_detail(run_id)
                if detail:
                    with st.expander(
                        f"Registration detail · {detail['website_host']}",
                        expanded=True,
                    ):
                        st.write(f"Website: {detail['target_url']}")
                        st.write(f"Status: {detail['status']}")
                        render_paginated_dataframe(
                            pd.DataFrame(detail["identities"]),
                            key=f"website_registration_identities_{run_id[:8]}",
                            alt="Emails used in the QA record",
                        )
        else:
            st.info("No website QA records have been saved yet.")
