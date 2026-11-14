from __future__ import annotations

import streamlit as st

from simuru_research.config.settings import Settings
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository
from simuru_research.ui.tabs import render_selected_page, render_sidebar_navigation

settings = Settings.from_env()
repository = SQLiteRepository(settings.database_path)
auth_qa_service = LocalAuthQAService(
    settings.database_path,
    email_domain="teguhharits.com",
)

st.set_page_config(
    page_title="Simuru Research",
    page_icon=":material/science:",
    layout="wide",
)

st.html(
    """
    <style>
        :root {
            --app-sidebar-width: calc(17.5rem - 34px);
        }
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        footer {
            display: none;
        }
        .stApp {
            background: #f5f6fa;
    }
    [data-testid="stMainBlockContainer"] {
        width: 100%;
        max-width: none;
        box-sizing: border-box;
        padding: 0 clamp(1rem, 2.2vw, 2.5rem) 3rem;
    }
    [data-testid="stColumn"] {
        min-width: 0;
    }
    .st-key-app-sidebar-expanded,
    .st-key-app-sidebar-collapsed {
        position: fixed;
        z-index: 1000;
        inset: 0 auto 0 0;
        height: 100dvh;
        box-sizing: border-box;
        overflow-x: hidden;
        overflow-y: auto;
        overscroll-behavior: contain;
        border: 0;
        border-right: 1px solid #e2e8f0;
        border-radius: 0;
        background: #ffffff;
        padding: 0.75rem;
        transition: width 180ms ease, box-shadow 180ms ease;
    }
    div.st-key-toggle_app_sidebar_open {
        z-index: 1001;
        width: 2.1875rem;
        margin: 0;
        transition: left 180ms ease, transform 180ms ease;
    }
    div.st-key-expand_sidebar_hover {
        position: fixed;
        z-index: 1001;
        top: 1rem;
        left: calc(var(--app-sidebar-width) - 1.09375rem);
        width: 2.1875rem;
        margin: 0;
        visibility: hidden;
        opacity: 0;
        pointer-events: none;
        transition: opacity 180ms ease, left 180ms ease;
    }
    body:has(.st-key-app-sidebar-collapsed:hover) div.st-key-expand_sidebar_hover,
    body:has(.st-key-app-sidebar-collapsed:focus-within) div.st-key-expand_sidebar_hover {
        visibility: visible;
        opacity: 1;
        pointer-events: auto;
    }
    div.st-key-expand_sidebar_hover button {
        position: relative;
        display: flex;
        width: 2.1875rem;
        min-width: 2.1875rem;
        height: 2.1875rem;
        min-height: 2.1875rem;
        padding: 0;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: #ffffff;
        box-shadow: none;
    }
    div.st-key-expand_sidebar_hover button::before {
        position: absolute;
        z-index: 0;
        inset: 0;
        border-radius: 50%;
        background: #696cff;
        box-shadow: 0 0.25rem 0.75rem #696cff55;
        content: "";
    }
    div.st-key-expand_sidebar_hover button::after {
        position: absolute;
        z-index: 1;
        top: 50%;
        left: 50%;
        width: 16px;
        height: 16px;
        background: currentColor;
        content: "";
        -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='white' viewBox='0 0 16 16'%3E%3Cpath fill-rule='evenodd' d='M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708'/%3E%3C/svg%3E") center / contain no-repeat;
        mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='white' viewBox='0 0 16 16'%3E%3Cpath fill-rule='evenodd' d='M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708'/%3E%3C/svg%3E") center / contain no-repeat;
        transform: translate(-50%, -50%) rotate(0deg);
    }
    div.st-key-expand_sidebar_hover button [data-testid="stIconMaterial"],
    div.st-key-expand_sidebar_hover button p {
        display: none;
    }
    div.st-key-toggle_app_sidebar_open button {
        position: relative;
        display: flex;
        width: 2.1875rem;
        min-width: 2.1875rem;
        height: 2.1875rem;
        min-height: 2.1875rem;
        padding: 0;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: #696cff;
        box-shadow: none;
    }
    div.st-key-toggle_app_sidebar_open button::before {
        position: absolute;
        z-index: 0;
        inset: 0;
        border-radius: 50%;
        background: #696cff;
        box-shadow: 0 0.25rem 0.75rem #696cff55;
        content: "";
        opacity: 0;
        transition: opacity 180ms ease;
    }
    div.st-key-toggle_app_sidebar_open button::after {
        position: absolute;
        z-index: 1;
        top: 50%;
        left: 50%;
        width: 16px;
        height: 16px;
        background: currentColor;
        content: "";
        -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='white' viewBox='0 0 16 16'%3E%3Cpath fill-rule='evenodd' d='M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708'/%3E%3C/svg%3E") center / contain no-repeat;
        mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='white' viewBox='0 0 16 16'%3E%3Cpath fill-rule='evenodd' d='M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708'/%3E%3C/svg%3E") center / contain no-repeat;
        opacity: 0;
        transform: translate(-50%, -50%) rotate(0deg);
        transition: opacity 180ms ease, transform 180ms ease;
    }
    div.st-key-toggle_app_sidebar_open button [data-testid="stIconMaterial"],
    div.st-key-toggle_app_sidebar_open button p {
        display: none;
    }
    :is(div.st-key-toggle_app_sidebar_open, div.st-key-expand_sidebar_hover) button {
        display: flex !important;
        width: 2.1875rem !important;
        min-width: 2.1875rem !important;
        max-width: 2.1875rem !important;
        height: 2.1875rem !important;
        min-height: 2.1875rem !important;
        max-height: 2.1875rem !important;
        aspect-ratio: 1 / 1 !important;
        box-sizing: border-box !important;
        flex: 0 0 2.1875rem !important;
        padding: 0 !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 50% !important;
    }
    :is(div.st-key-toggle_app_sidebar_open, div.st-key-expand_sidebar_hover) button::before {
        width: 100%;
        height: 100%;
        border-radius: 50% !important;
    }
    :is(div.st-key-toggle_app_sidebar_open, div.st-key-expand_sidebar_hover) button::after {
        top: 50% !important;
        left: 50% !important;
        width: 16px !important;
        height: 16px !important;
    }
    body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open {
        position: fixed;
        top: 1rem;
        left: calc(var(--app-sidebar-width) - 1.09375rem);
    }
    body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open button {
        color: #ffffff;
    }
    body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open button::before {
        opacity: 1;
    }
    body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open button::after {
        opacity: 1;
        transform: translate(-50%, -50%) rotate(180deg);
        animation: app-sidebar-chevron-rotate 180ms ease-out both;
    }
    div.st-key-toggle_app_sidebar_closed {
        width: 2.1875rem;
        margin: 0;
    }
    div.st-key-toggle_app_sidebar_closed button {
        display: flex;
        width: 2.1875rem;
        min-width: 2.1875rem;
        height: 2.1875rem;
        min-height: 2.1875rem;
        padding: 0;
        align-items: center;
        justify-content: center;
        border: 0;
        background: transparent;
        color: #696cff;
        box-shadow: none;
    }
    div.st-key-toggle_app_sidebar_closed button p {
        display: none;
    }
    div.st-key-toggle_app_sidebar_closed [data-testid="stIconMaterial"] {
        font-size: 1.75rem !important;
    }
    body:has(.st-key-app-sidebar-collapsed) div.st-key-toggle_app_sidebar_closed {
        position: fixed;
        top: 1.15625rem;
        left: calc(4.5rem + 9px);
    }
    div.st-key-toggle_app_sidebar_open button:hover,
    div.st-key-toggle_app_sidebar_closed button:hover {
        border: 0;
        background: transparent;
    }
    .st-key-close_mobile_sidebar {
        display: none;
    }
    @keyframes app-sidebar-chevron-rotate {
        from { transform: translate(-50%, -50%) rotate(0deg); }
        to { transform: translate(-50%, -50%) rotate(180deg); }
    }
    @keyframes app-sidebar-menu-rotate {
        from { transform: rotate(-90deg); }
        to { transform: rotate(0deg); }
    }
    .st-key-app-topbar-heading {
        display: flex;
        align-items: center;
        gap: 9px !important;
        min-height: 2.75rem;
        min-width: 0;
        overflow: visible;
    }
    .st-key-app-topbar-heading [data-testid="stMarkdownContainer"] {
        display: flex;
        height: 100%;
        align-items: center;
        overflow: visible;
    }
    .st-key-app-topbar-heading [data-testid="stMarkdownContainer"] p {
        margin: 0;
        color: #384253;
        font-size: 1.15rem;
        line-height: 1.4;
        overflow: visible;
    }
    .st-key-app-sidebar-brand p {
        width: 100%;
        justify-content: center;
    }
    .st-key-app-sidebar-brand {
        padding-top: 0.8rem;
    }
    .st-key-app-sidebar-brand [data-testid="stMarkdownContainer"] {
        width: 100%;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] {
        position: relative;
        margin-left: 3px;
        margin-right: -0.75rem;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button {
        display: flex !important;
        align-items: center !important;
        gap: 0.75rem !important;
        width: 100% !important;
        justify-content: flex-start !important;
        text-align: left !important;
        padding: 0.75rem 1rem !important;
        white-space: nowrap !important;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button > div {
        display: flex !important;
        flex: 1 1 auto;
        align-items: center !important;
        justify-content: flex-start !important;
        min-width: 0;
        width: 100% !important;
        text-align: left !important;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button > div > [data-testid="stMarkdownContainer"] {
        display: block !important;
        flex: 1 1 auto;
        min-width: 0;
        width: auto !important;
        text-align: left !important;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button [data-testid="stMarkdownContainer"] {
        display: block !important;
        flex: 1 1 auto;
        min-width: 0;
        width: auto !important;
        text-align: left !important;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button p {
        display: block !important;
        width: 100% !important;
        margin: 0 !important;
        justify-content: flex-start !important;
        text-align: left !important;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button [data-testid="stIconMaterial"] {
        flex: 0 0 auto;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"]:has(button[data-testid="stBaseButton-primary"])::after {
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        width: 5px;
        border-radius: 3px 0 0 3px;
        background: #696cff;
        content: "";
        pointer-events: none;
    }
    :is(.st-key-app-sidebar-expanded, .st-key-app-sidebar-collapsed:hover, .st-key-app-sidebar-collapsed:focus-within) [class*="st-key-navigate_"] button[data-testid="stBaseButton-primary"] {
        border-color: transparent !important;
        border-radius: 0.65rem !important;
        background: #e9e7fd !important;
        color: #696cff !important;
        box-shadow: none !important;
    }
    .st-key-app-sidebar-collapsed {
        width: 4.5rem;
        overflow-y: hidden;
        padding: 0.75rem 0.35rem;
    }
    .st-key-app-sidebar-collapsed:hover,
    .st-key-app-sidebar-collapsed:focus-within {
        width: var(--app-sidebar-width);
        overflow-y: auto;
        box-shadow: 0 0.5rem 1.5rem #33415526;
    }
    .st-key-app-sidebar-collapsed p {
        font-size: 0;
        line-height: 0;
    }
    .st-key-app-sidebar-collapsed:hover p,
    .st-key-app-sidebar-collapsed:focus-within p {
        font-size: inherit;
        line-height: inherit;
    }
    .st-key-app-sidebar-collapsed .stButton button {
        min-height: 2.8rem;
        justify-content: center;
        overflow: hidden;
        white-space: nowrap;
    }
    .st-key-app-sidebar-collapsed:hover .stButton button,
    .st-key-app-sidebar-collapsed:focus-within .stButton button {
        justify-content: flex-start;
    }
    .st-key-app-sidebar-expanded {
        width: var(--app-sidebar-width);
    }
    .st-key-app-sidebar-expanded .stButton button,
    .st-key-app-sidebar-collapsed .stButton button {
        border-color: transparent;
        border-radius: 0.65rem;
    }
    .st-key-app-sidebar-expanded .stButton button:hover,
    .st-key-app-sidebar-collapsed .stButton button:hover {
        border-color: #e2e8f0;
    }
    .st-key-app-sidebar-brand p {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        white-space: nowrap;
    }
    .st-key-app-sidebar-brand span {
        font-size: 1.5rem;
        line-height: 1;
        color: #696cff;
    }
    .st-key-app-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        width: auto !important;
        min-height: calc(4.5rem + 3px);
        overflow: visible;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.2rem;
        z-index: 900;
        margin-bottom: 1rem;
        border: 1px solid #e8eaf1;
        border-radius: 0 0 0.75rem 0.75rem;
        background: #ffffffee;
        box-shadow: 0 0.15rem 0.5rem #33415512;
        padding: 0.5rem 2rem 0.5rem calc(var(--app-sidebar-width) + 2.5rem);
        backdrop-filter: blur(12px);
    }
    .st-key-app-topbar p {
        margin-bottom: 0;
    }
    body:has(.st-key-app-sidebar-collapsed) .st-key-app-topbar {
        padding-left: calc(4.5rem + 2.1875rem + 9px);
    }
    .st-key-overview-hero {
        min-height: 12rem;
        border: 0;
        border-radius: 0.85rem;
        background: linear-gradient(115deg, #ffffff 0%, #f0efff 100%);
        box-shadow: 0 0.25rem 1rem #33415512;
        padding: 1.5rem;
    }
    .st-key-overview-hero h3 {
        color: #696cff;
    }
    .st-key-overview-latest-card,
    .st-key-overview-active-emails-card,
    .st-key-overview-run-summary {
        min-height: 12rem;
        border-color: #eceef4;
        border-radius: 0.85rem;
        background: #ffffff;
        box-shadow: 0 0.25rem 1rem #33415512;
    }
    .st-key-overview-activity-chart,
    .st-key-overview-run-summary {
        border-color: #eceef4;
        border-radius: 0.85rem;
        border: 1px solid #e2e8f0;
        background: #ffffff;
        box-shadow: 0 0.25rem 1rem #33415512;
    }
    .st-key-app-breadcrumbs {
        width: 100%;
        max-width: 1500px;
        box-sizing: border-box;
        margin-left: auto;
        margin-right: auto;
        min-height: 2rem;
        align-items: center;
        color: #64748b;
        margin-bottom: 0.75rem;
    }
    .st-key-app-breadcrumbs .stButton button {
        min-height: 2rem;
        border: 0;
        background: transparent;
        color: #64748b;
        padding: 0 0.25rem;
    }
    .st-key-app-breadcrumbs .stButton button:hover {
        color: #696cff;
    }
    .st-key-app-page-card {
        width: 100%;
        max-width: 1500px;
        min-width: 0;
        box-sizing: border-box;
        margin-left: auto;
        margin-right: auto;
        border: 1px solid #e6e9f0;
        border-radius: 1rem;
        background: #ffffff;
        box-shadow: 0 0.25rem 1rem #33415512, 0 0.05rem 0.15rem #33415508;
        padding: clamp(1.25rem, 2vw, 2rem);
    }
    .st-key-domain-email-list .stButton button {
        overflow: hidden;
    }
    .st-key-domain-email-list .stButton button p {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    @media (max-width: 1024px) {
        div.st-key-expand_sidebar_hover {
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        .st-key-app-sidebar-collapsed {
            width: 4.5rem;
            overflow-y: hidden;
            padding: 0.75rem 0.35rem;
        }
        .st-key-app-sidebar-expanded {
            width: min(var(--app-sidebar-width), calc(100vw - 3.5rem));
            overflow-y: auto;
            padding: 0.75rem;
            box-shadow: 0 0.75rem 2rem #0f172a33;
        }
        .st-key-app-sidebar-collapsed p {
            font-size: 0;
            line-height: 0;
        }
        .st-key-app-sidebar-expanded .stButton button {
            min-height: 2.8rem;
            justify-content: flex-start;
            overflow: hidden;
            white-space: nowrap;
        }
        .st-key-app-sidebar-collapsed .stButton button {
            min-height: 2.8rem;
            justify-content: center;
            overflow: hidden;
            white-space: nowrap;
        }
        .st-key-app-sidebar-expanded .st-key-app-sidebar-brand p {
            justify-content: center;
        }
        .st-key-app-sidebar-collapsed .st-key-app-sidebar-brand p {
            justify-content: center;
        }
        .st-key-app-sidebar-collapsed:hover,
        .st-key-app-sidebar-collapsed:focus-within {
            width: 4.5rem;
            overflow-y: hidden;
            box-shadow: none;
        }
        .st-key-app-sidebar-collapsed:hover p,
        .st-key-app-sidebar-collapsed:focus-within p {
            font-size: 0;
            line-height: 0;
        }
        .st-key-app-sidebar-collapsed:hover .stButton button,
        .st-key-app-sidebar-collapsed:focus-within .stButton button {
            justify-content: center;
        }
        .st-key-app-sidebar-collapsed:hover .st-key-app-sidebar-brand p,
        .st-key-app-sidebar-collapsed:focus-within .st-key-app-sidebar-brand p {
            justify-content: center;
        }
        body:has(.st-key-app-sidebar-expanded) .stApp::after {
            position: fixed;
            z-index: 999;
            inset: 0;
            background: #0f172a66;
            content: "";
            pointer-events: none;
        }
        body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open {
            left: min(calc(var(--app-sidebar-width) - 1.09375rem), calc(100vw - 4.59375rem));
        }
        body:has(.st-key-app-sidebar-collapsed) div.st-key-toggle_app_sidebar_closed {
            left: calc(4.5rem + 9px);
        }
        .st-key-app-topbar {
            padding-left: 5.5rem;
            padding-right: 1rem;
        }
        body:has(.st-key-app-sidebar-collapsed) .st-key-app-topbar {
            padding-left: calc(4.5rem + 2.1875rem + 18px) !important;
        }
        .st-key-app-page-card {
            border-radius: 0.85rem;
            padding: 1.25rem;
        }
        body:has(.st-key-app-sidebar-collapsed) .stApp::after {
            display: none;
        }
    }
    @media (max-width: 640px) {
        .st-key-app-topbar {
            padding: 0.6rem 0.75rem 0.6rem 4.75rem;
        }
        body:has(.st-key-app-sidebar-collapsed) .st-key-app-topbar {
            padding-left: calc(1rem + 2.1875rem + 9px) !important;
        }
        body:has(.st-key-app-sidebar-collapsed) div.st-key-toggle_app_sidebar_closed {
            left: 1rem;
            top: 1.15625rem;
        }
        .st-key-app-topbar p {
            margin-bottom: 0;
        }
        .st-key-app-page-card {
            border-radius: 0.75rem;
            padding: 1rem;
        }
        .st-key-app-sidebar-collapsed {
            width: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            border: 0 !important;
            visibility: hidden;
            pointer-events: none;
        }
        .st-key-app-sidebar-expanded {
            width: min(20rem, calc(100vw - 3rem)) !important;
            padding: 0.75rem !important;
            box-shadow: 0 0.75rem 2rem #0f172a33;
        }
        .st-key-app-sidebar-expanded .st-key-close_mobile_sidebar {
            position: absolute;
            z-index: 1;
            top: 0.75rem;
            right: 0.75rem;
            display: block;
        }
        .st-key-app-sidebar-expanded .st-key-close_mobile_sidebar button {
            width: 2.25rem;
            min-width: 2.25rem;
            height: 2.25rem;
            min-height: 2.25rem;
            justify-content: center;
            padding: 0;
        }
        div.st-key-toggle_app_sidebar_open {
            z-index: auto !important;
        }
        body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open button::before,
        body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open button::after {
            opacity: 0;
        }
        body:has(.st-key-app-sidebar-expanded) div.st-key-toggle_app_sidebar_open button [data-testid="stIconMaterial"] {
            display: inline-flex;
            color: #696cff;
            font-size: 1.75rem !important;
        }
        .st-key-app-breadcrumbs {
            margin-bottom: 0.5rem;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .st-key-app-sidebar-expanded,
        .st-key-app-sidebar-collapsed {
            transition: none;
        }
    }
    </style>
    """
)

st.session_state.setdefault("app_sidebar_collapsed", False)
sidebar_collapsed = st.session_state.get("app_sidebar_collapsed", False)


def _toggle_app_sidebar() -> None:
    st.session_state["app_sidebar_collapsed"] = not st.session_state.get(
        "app_sidebar_collapsed",
        False,
    )


def _expand_sidebar_from_hover() -> None:
    st.session_state["app_sidebar_collapsed"] = False


sidebar_column, content_column = st.columns(
    [0.6, 9.4] if sidebar_collapsed else [1.9, 8.1],
    gap="small",
)
with sidebar_column:
    sidebar_key = (
        "app-sidebar-collapsed" if sidebar_collapsed else "app-sidebar-expanded"
    )
    with st.container(key=sidebar_key):
        with st.container(key="app-sidebar-brand"):
            st.markdown(":material/science: **Simuru Research**")
        if sidebar_collapsed:
            st.button(
                "Expand sidebar",
                icon=":material/chevron_left:",
                key="expand_sidebar_hover",
                width="content",
                on_click=_expand_sidebar_from_hover,
            )
        if not sidebar_collapsed:
            st.button(
                "Close sidebar",
                icon=":material/close:",
                key="close_mobile_sidebar",
                width="content",
                on_click=_toggle_app_sidebar,
            )
        render_sidebar_navigation()

with content_column:
    current_page = st.session_state.get("current_page", "Overview")
    page_labels = {
        "Overview": "Dashboard",
        "Mailbox": "List email",
        "Sandbox Batch": "Sandbox batch",
        "Registration QA": "Registration QA",
        "Website Registration": "Website Registration",
        "Run History & Export": "Run history & export",
        "SIMURU API": "SIMURU API",
    }
    if not sidebar_collapsed:
        st.button(
            "Collapse sidebar",
            icon=":material/chevron_left:",
            key="toggle_app_sidebar_open",
            width="content",
            on_click=_toggle_app_sidebar,
        )
    with st.container(key="app-topbar"):
        with st.container(
            key="app-topbar-heading",
            horizontal=True,
            vertical_alignment="center",
            gap="small",
            wrap=False,
        ):
            if sidebar_collapsed:
                st.button(
                    "Open sidebar",
                    icon=":material/menu:",
                    key="toggle_app_sidebar_closed",
                    width="content",
                    on_click=_toggle_app_sidebar,
                )
            st.markdown(f"**{page_labels.get(current_page, 'Dashboard')}**")
    st.space(96)
    render_selected_page(
        settings=settings,
        repository=repository,
        auth_qa_service=auth_qa_service,
    )
