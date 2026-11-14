from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _render_navigation() -> None:
    from simuru_research.ui.tabs import render_sidebar_navigation

    render_sidebar_navigation()


def test_sidebar_exposes_remaining_pages_without_removed_feature_menus():
    app = AppTest.from_function(_render_navigation).run()

    assert not app.exception
    button_keys = {button.key for button in app.button}
    assert "navigate_overview" in button_keys
    assert "navigate_mailbox" in button_keys
    assert "navigate_sandbox_batch" in button_keys
    assert "navigate_registration_qa" in button_keys
    assert "navigate_team_accounts" not in button_keys
    assert "navigate_website_automation" not in button_keys
    assert len(app.expander) == 0


def _render_framed_page() -> None:
    from types import SimpleNamespace

    import streamlit as st

    from simuru_research.ui.tabs import render_selected_page

    st.session_state["current_page"] = "Sandbox Batch"
    repository = SimpleNamespace(list_runs=lambda limit=10: [])
    render_selected_page(
        settings=SimpleNamespace(default_total_jobs=40, default_max_workers=3),
        repository=repository,
        auth_qa_service=None,
    )


def test_each_page_gets_a_breadcrumb_and_outer_card():
    app = AppTest.from_function(_render_framed_page).run()

    assert not app.exception
    assert any(item.key == "breadcrumb_overview" for item in app.button)
    assert any(item.value == "Run synthetic QA batch" for item in app.subheader)
    assert any(item.key == "app-page-card" for item in app.get("container"))
    assert {item.key for item in app.number_input} >= {
        "sandbox_total_jobs",
        "sandbox_max_workers",
    }
