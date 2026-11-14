from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import streamlit as st

DEFAULT_PAGE_SIZE = 6


def paginate_items[T](
    items: Sequence[T],
    page: int,
    page_size: int,
) -> tuple[list[T], int, int]:
    if page_size < 1:
        raise ValueError("page_size must be greater than zero.")
    page_count = max(1, (len(items) + page_size - 1) // page_size)
    current_page = min(max(1, page), page_count)
    start = (current_page - 1) * page_size
    return list(items[start : start + page_size]), current_page, page_count


def render_pagination(
    *,
    total_items: int,
    page_size: int,
    key: str,
) -> int:
    if page_size < 1:
        raise ValueError("page_size must be greater than zero.")
    page_count = max(1, (total_items + page_size - 1) // page_size)
    page_key = f"{key}_page"
    current_page = st.session_state.get(page_key, 1)
    if not isinstance(current_page, int):
        current_page = 1
    current_page = min(max(1, current_page), page_count)
    st.session_state[page_key] = current_page

    with st.container(
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
        gap="small",
        wrap=False,
    ):
        st.button(
            "‹",
            key=f"{key}_previous",
            help="Previous page",
            disabled=current_page <= 1,
            on_click=_set_page,
            args=(page_key, current_page - 1),
            width="content",
        )
        for index, page_number in enumerate(
            _visible_pages(current_page, page_count)
        ):
            if page_number is None:
                st.button(
                    "…",
                    key=f"{key}_ellipsis_{index}",
                    disabled=True,
                    width="content",
                )
                continue
            st.button(
                str(page_number),
                key=f"{key}_number_{page_number}",
                type="primary" if page_number == current_page else "secondary",
                on_click=_set_page,
                args=(page_key, page_number),
                width="content",
            )
        st.button(
            "›",
            key=f"{key}_next",
            help="Next page",
            disabled=current_page >= page_count,
            on_click=_set_page,
            args=(page_key, current_page + 1),
            width="content",
        )
    return current_page


def render_paginated_dataframe(
    dataframe: pd.DataFrame,
    *,
    key: str,
    alt: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    hide_index: bool = True,
) -> None:
    page_key = f"{key}_page"
    page = st.session_state.get(page_key, 1)
    if not isinstance(page, int):
        page = 1
    _, page, _ = paginate_items(dataframe.to_dict("records"), page, page_size)
    st.session_state[page_key] = page
    page_rows, _, _ = paginate_items(dataframe.to_dict("records"), page, page_size)
    st.dataframe(
        pd.DataFrame(page_rows, columns=dataframe.columns),
        width="stretch",
        hide_index=hide_index,
        alt=alt,
    )
    render_pagination(
        total_items=len(dataframe),
        page_size=page_size,
        key=key,
    )


def _set_page(page_key: str, page: int) -> None:
    st.session_state[page_key] = page


def _visible_pages(current_page: int, page_count: int) -> list[int | None]:
    if page_count <= 5:
        return list(range(1, page_count + 1))
    if current_page <= 2:
        return [1, 2, 3, None, page_count - 1, page_count]
    if current_page >= page_count - 1:
        return [1, None, page_count - 2, page_count - 1, page_count]
    return [
        1,
        None,
        current_page - 1,
        current_page,
        current_page + 1,
        None,
        page_count,
    ]
