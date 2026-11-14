from __future__ import annotations

from simuru_research.providers.cpanel_mailboxes import CpanelMailboxOperations


class CpanelBrowserMailboxManager(CpanelMailboxOperations):
    """Facade for cPanel session and mailbox management operations."""
