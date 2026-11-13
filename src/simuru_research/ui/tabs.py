from __future__ import annotations

import streamlit as st

from simuru_research.ui.api_tab import render_api_tab
from simuru_research.ui.history_tab import render_history_tab
from simuru_research.ui.mailbox_tab import render_mailbox_tab
from simuru_research.ui.overview_tab import render_overview_tab
from simuru_research.ui.registration_qa_tab import render_registration_qa_tab
from simuru_research.ui.sandbox_tab import render_sandbox_tab
from simuru_research.ui.team_tab import render_team_tab
from simuru_research.ui.website_tab import render_website_tab


def render_all_tabs(
    settings,
    repository,
    team_accounts,
    auth_qa_service,
    total_jobs: int,
    max_workers: int,
) -> None:
    tabs = st.tabs(
        [
            "Overview",
            "Team Accounts",
            "Sandbox Batch",
            "Mailbox Manager",
            "Website Automation",
            "Registration QA",
            "Run History & Export",
            "SIMURU API",
        ]
    )
    (
        overview_tab,
        team_tab,
        sandbox_tab,
        mailbox_tab,
        website_tab,
        registration_qa_tab,
        history_tab,
        api_tab,
    ) = tabs

    with overview_tab:
        render_overview_tab(repository, team_accounts)

    with team_tab:
        render_team_tab(team_accounts)

    with sandbox_tab:
        render_sandbox_tab(repository, total_jobs, max_workers)

    with mailbox_tab:
        render_mailbox_tab(settings)

    with website_tab:
        render_website_tab()

    with registration_qa_tab:
        render_registration_qa_tab(repository, auth_qa_service)

    with history_tab:
        render_history_tab(repository)

    with api_tab:
        render_api_tab(settings)