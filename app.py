from __future__ import annotations

import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository
from simuru_research.storage.team_accounts import TeamAccountRegistry
from simuru_research.ui.tabs import render_all_tabs

settings = Settings.from_env()
repository = SQLiteRepository(settings.database_path)
team_accounts = TeamAccountRegistry(settings.database_path)
auth_qa_service = LocalAuthQAService(settings.database_path)

st.set_page_config(page_title="Simuru Research", page_icon="🧪", layout="wide")
st.title("Simuru Research Lab")
st.caption(
    "Local team registry · SIMURU API research · "
    "Registration QA · SQLite history"
)

with st.sidebar:
    st.subheader("Sandbox configuration")
    total_jobs = st.number_input(
        "Synthetic test identities",
        min_value=1,
        max_value=100,
        value=min(settings.default_total_jobs, 100),
        step=1,
    )
    max_workers = st.number_input(
        "Concurrent workers",
        min_value=1,
        max_value=10,
        value=min(settings.default_max_workers, 10),
        step=1,
        help="Bounded local workers. No browser sessions or external signups.",
    )
    st.divider()
    st.caption(
        "Registration QA uses local-only test identities "
        "and a local OTP outbox."
    )
    st.caption(
        "No Instagram signup, external OTP retrieval, "
        "or provider rental is performed."
    )

# Render seluruh tab antarmuka dari modul terpisah
render_all_tabs(
    settings=settings,
    repository=repository,
    team_accounts=team_accounts,
    auth_qa_service=auth_qa_service,
    total_jobs=int(total_jobs),
    max_workers=int(max_workers),
)
