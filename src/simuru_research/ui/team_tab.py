from __future__ import annotations

import pandas as pd
import streamlit as st


def render_team_tab(team_accounts) -> None:
    st.subheader("Team Instagram Account Registry")
    st.write(
        "Catat akun Instagram yang sudah ada dan memang dimiliki atau dikelola "
        "dengan izin oleh tim. Registry ini tidak membuat akun, login, atau "
        "mengambil alih akun Instagram."
    )
    st.warning(
        "Jangan masukkan password, kode OTP, nomor telepon, email pribadi, "
        "session cookie, atau access token ke registry/CSV ini. "
        "Pemilik akun harus menyetujui pencatatan username."
    )

    counts = team_accounts.count_by_type()
    total_accounts = sum(counts.values())
    metric_columns = st.columns(4)
    metric_columns[0].metric("Total registered", total_accounts)
    metric_columns[1].metric("Personal · manual only", counts["personal"])
    metric_columns[2].metric("Creator · OAuth pending", counts["creator"])
    metric_columns[3].metric("Business · OAuth pending", counts["business"])

    with st.form("add_team_account_form", clear_on_submit=True):
        st.markdown("**Register an existing team account**")
        first, second = st.columns(2)
        with first:
            username = st.text_input(
                "Instagram username",
                placeholder="team_account",
            )
            owner_label = st.text_input(
                "Owner / team label",
                placeholder="Marketing Team",
            )
        with second:
            account_type = st.selectbox(
                "Account type",
                ["personal", "creator", "business"],
                help=(
                    "Personal accounts are recorded only; official API access "
                    "requires Creator or Business."
                ),
            )
            notes = st.text_input("Notes (optional)", placeholder="Pilot account")
        owner_approved = st.checkbox(
            "I confirm the owner has authorized our team to "
            "record and manage this account."
        )
        submitted = st.form_submit_button("Add existing account", type="primary")

    if submitted:
        try:
            inserted = team_accounts.add_account(
                username=username,
                owner_label=owner_label,
                account_type=account_type,
                owner_approved=owner_approved,
                notes=notes,
            )
            if inserted:
                clean_name = username.strip().removeprefix("@")
                st.success(f"@{clean_name} added to the local registry.")
            else:
                st.info("Username already exists in the registry.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    st.markdown("**Bulk import existing accounts from CSV**")
    st.caption(
        "Required columns: username, owner_label, account_type, "
        "owner_approved, notes. Only rows with owner_approved=true are imported."
    )
    csv_template = (
        "username,owner_label,account_type,owner_approved,notes\n"
        "sample_team_account,Marketing Team,personal,true,"
        "Replace with an authorized account\n"
    )
    st.download_button(
        "Download CSV template",
        data=csv_template,
        file_name="simuru-team-accounts-template.csv",
        mime="text/csv",
    )
    uploaded_csv = st.file_uploader(
        "Choose team account CSV",
        type=["csv"],
        key="team_account_csv",
    )
    import_confirmed = st.checkbox(
        "I confirm every imported account is owned by the team or explicitly "
        "authorized by its owner."
    )
    if st.button(
        "Import authorized accounts",
        type="primary",
        disabled=uploaded_csv is None,
    ):
        if not import_confirmed:
            st.error("Confirm account ownership/authorization before importing.")
        else:
            try:
                csv_content = uploaded_csv.getvalue().decode("utf-8-sig")
                result = team_accounts.import_csv(csv_content, confirmed=True)
                st.success(
                    f"Imported: {result['imported']} · "
                    f"Duplicates: {result['duplicates']} · "
                    f"Unapproved skipped: {result['unauthorized']} · "
                    f"Invalid skipped: {result['invalid']}"
                )
                st.rerun()
            except (UnicodeDecodeError, ValueError) as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("Registered team accounts")
    accounts = team_accounts.list_accounts()
    if accounts:
        account_frame = pd.DataFrame(accounts)
        account_frame["owner_approved"] = account_frame[
            "owner_approved"
        ].astype(bool)
        st.dataframe(
            account_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "owner_approved": st.column_config.CheckboxColumn(
                    "Owner approved",
                    disabled=True,
                )
            },
        )
        st.download_button(
            "Export team account registry",
            data=team_accounts.export_csv(),
            file_name="simuru-team-accounts.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "Belum ada akun yang dicatat. "
            "Tambahkan satu akun pilot atau import CSV."
        )

    st.subheader("Meta API eligibility")
    st.markdown(
        "- **Personal:** registry-only. Instagram's official API does not "
        "provide access to consumer/personal accounts.\n"
        "- **Creator / Business:** eligible to proceed to Meta OAuth after the "
        "Instagram API product, permissions, and app roles are configured.\n"
        "- This release does not request passwords, automate sign-up, rent numbers, "
        "retrieve OTPs, or create Instagram accounts."
    )
    st.markdown(
        "[Meta for Developers](https://developers.facebook.com/apps/) · "
        "[Instagram API documentation]"
        "(https://www.postman.com/meta/instagram/documentation/)"
    )