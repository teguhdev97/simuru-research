from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


@contextmanager
def menu_card(title: str, subtitle: str | None = None) -> Iterator[None]:
    """Render a reusable white, rounded card for a dashboard menu section."""
    with st.container(border=True, key=f"card_{title.lower().replace(' ', '_')}"):
        st.subheader(title)
        if subtitle:
            st.caption(subtitle)
        yield
