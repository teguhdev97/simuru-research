from __future__ import annotations

from streamlit.testing.v1 import AppTest

from simuru_research.ui.email_multi_select import _valid_selection


def test_email_multi_select_keeps_unique_known_options_only():
    options = ["one@example.test", "two@example.test"]

    assert _valid_selection(
        ["one@example.test", "one@example.test", "unknown@example.test"],
        options,
    ) == ["one@example.test"]
    assert _valid_selection("one@example.test", options) == []
    assert _valid_selection(None, options) == []


def test_email_multi_select_renders_in_streamlit_app_test():
    def render() -> None:
        import streamlit as st

        from simuru_research.ui.email_multi_select import email_multi_select

        selected = email_multi_select(
            "Mailbox",
            ["one@example.test", "two@example.test"],
            key="test_email_multi_select",
            max_selections=2,
        )
        st.write(selected)

    app = AppTest.from_function(render).run()

    assert not app.exception
