from __future__ import annotations

import math

import pandas as pd
import streamlit as st

PAGE_SIZE = 6


def _visible_pages(current_page: int, total_pages: int) -> list[int | None]:
    if total_pages <= 5:
        return list(range(1, total_pages + 1))

    pages = {1, 2, total_pages - 1, total_pages, current_page}
    visible = sorted(page for page in pages if 1 <= page <= total_pages)
    result: list[int | None] = []
    for index, page in enumerate(visible):
        if index and page - visible[index - 1] > 1:
            result.append(None)
        result.append(page)
    return result


def render_paginated_table(
    data: pd.DataFrame | list[dict],
    *,
    key: str,
    page_size: int = PAGE_SIZE,
) -> None:
    """Render a white table and compact, right-aligned pagination controls."""
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    frame = frame.copy()
    for column in frame.columns:
        if column.lower().endswith(('_at', '_date', 'date')):
            parsed = pd.to_datetime(frame[column], errors="coerce", utc=True)
            valid = parsed.notna()
            frame.loc[valid, column] = parsed.loc[valid].dt.strftime("%d %b %Y")
    total_pages = max(1, math.ceil(len(frame) / page_size))
    state_key = f"table_page_{key}"
    current_page = min(max(1, int(st.session_state.get(state_key, 1))), total_pages)
    st.session_state[state_key] = current_page

    start = (current_page - 1) * page_size
    page_frame = frame.iloc[start : start + page_size]
    styled_frame = page_frame.style.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", "#ffffff"),
                    ("font-weight", "700"),
                    ("font-size", "1.25em"),
                    ("color", "#566a7f"),
                ],
            },
            {
                "selector": "td",
                "props": [("background-color", "#ffffff"), ("color", "#566a7f")],
            },
        ]
    )
    styled_frame = styled_frame.set_properties(
        **{"background-color": "#ffffff", "color": "#566a7f"}
    )
    styled_frame = styled_frame.hide(axis="index")
    st.table(styled_frame)

    if total_pages == 1:
        return

    items: list[tuple[str, int | None]] = [("‹", max(1, current_page - 1))]
    items.extend(
        ("…" if page is None else str(page), page)
        for page in _visible_pages(current_page, total_pages)
    )
    items.append(("›", min(total_pages, current_page + 1)))
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        for index, (label, page) in enumerate(items):
            if page is None:
                st.markdown(
                    f'<span class="pagination-ellipsis">{label}</span>',
                    unsafe_allow_html=True,
                )
                continue
            selected = label.isdigit() and page == current_page
            if st.button(
                label,
                key=f"pagination_{key}_{index}_{page}",
                type="primary" if selected else "secondary",
                disabled=(label == "‹" and current_page == 1)
                or (label == "›" and current_page == total_pages),
                help="Previous page" if label == "‹" else "Next page" if label == "›" else None,
            ) and page != current_page:
                st.session_state[state_key] = page
                st.rerun()
