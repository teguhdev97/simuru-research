from __future__ import annotations

from streamlit.testing.v1 import AppTest

from simuru_research.ui.pagination import _visible_pages, paginate_items


def _render_pagination() -> None:
    import streamlit as st

    from simuru_research.ui.pagination import render_pagination

    render_pagination(total_items=36, page_size=6, key="test_pagination")
    st.caption(f"Current page: {st.session_state['test_pagination_page']}")


def test_pagination_shows_requested_first_page_pattern_for_six_pages():
    assert _visible_pages(1, 6) == [1, 2, 3, None, 5, 6]


def test_pagination_keeps_middle_and_last_pages_reachable():
    assert _visible_pages(4, 10) == [1, None, 3, 4, 5, None, 10]
    assert _visible_pages(10, 10) == [1, None, 8, 9, 10]


def test_paginate_items_clamps_page_and_returns_page_count():
    items = list(range(13))

    assert paginate_items(items, 99, 6) == ([12], 3, 3)


def test_numbered_pagination_updates_the_selected_page():
    app = AppTest.from_function(_render_pagination).run()

    assert not app.exception
    app.button(key="test_pagination_number_2").click().run()

    assert not app.exception
    assert app.session_state["test_pagination_page"] == 2
