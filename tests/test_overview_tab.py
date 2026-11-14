from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _render_dashboard() -> None:
    import streamlit as st

    from simuru_research.ui.overview_tab import render_overview_tab

    class Repository:
        def list_runs(self, limit=10):
            return [
                {
                    "run_id": "run-12345678",
                    "total_jobs": 5,
                    "passed": 4,
                    "failed": 1,
                    "started_at": "2026-11-14T09:00:00Z",
                }
            ][:limit]

        def list_results(self, run_id):
            return [
                {
                    "job_index": index,
                    "username": f"qa-user-{index}",
                    "email": f"qa-{index}@example.test",
                    "phone": "",
                    "status": "passed",
                    "duration_ms": 120.0,
                    "error": None,
                    "created_at": "2026-11-14T09:00:00Z",
                }
                for index in range(1, 14)
            ]

    st.session_state["domain_email_addresses"] = [
        f"active-{index}@example.test" for index in range(8)
    ]
    render_overview_tab(Repository())


def test_overview_renders_active_email_card_and_opens_list_email():
    app = AppTest.from_function(_render_dashboard).run(timeout=10)

    assert not app.exception
    assert any(item.value == "Research workspace" for item in app.subheader)
    assert any(item.value == "Latest run details" for item in app.subheader)
    assert any(str(item.value) == "8" for item in app.metric)

    app.button(key="overview_open_active_emails").click().run()

    assert app.session_state["current_page"] == "Mailbox"
    assert not app.exception


def test_latest_run_table_uses_numbered_six_row_pagination():
    app = AppTest.from_function(_render_dashboard).run(timeout=10)

    assert not app.exception
    assert len(app.dataframe[0].value) == 6
    app.button(key="overview_results_pagination_number_2").click().run()

    assert not app.exception
    assert app.session_state["overview_results_pagination_page"] == 2
    assert len(app.dataframe[0].value) == 6
    assert app.dataframe[0].value.iloc[0]["job_index"] == 7
