from __future__ import annotations

from simuru_research.providers.cpanel_mailboxes import CpanelMailboxOperations
from simuru_research.providers.cpanel_website_qa import CpanelWebsiteQA


class CpanelBrowserMailboxManager(CpanelMailboxOperations, CpanelWebsiteQA):
    """Facade for cPanel session, mailbox management, and website QA operations."""
