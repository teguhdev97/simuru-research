from __future__ import annotations

import pytest

from simuru_research.engine.mailbox_batch import FiveMailboxBatchRunner
from simuru_research.providers.mailbox import MailboxError, MailboxSettings
from simuru_research.storage.database import SQLiteRepository


def settings(addresses):
    return MailboxSettings(
        domain="teguhharits.com",
        addresses=tuple(addresses),
        imap_host="imap.example.test",
        imap_port=993,
        smtp_host="smtp.example.test",
        smtp_port=465,
        username="qa@teguhharits.com",
        password="test-only",
        sender_allowlist=("noreply@localhost.test",),
        subject_keywords=("verification",),
    )


def test_batch_registers_exactly_five_mailboxes_in_history(tmp_path):
    addresses = [f"qa0{i}@teguhharits.com" for i in range(1, 6)]
    repository = SQLiteRepository(tmp_path / "qa.sqlite3")

    summary = FiveMailboxBatchRunner(repository, settings(addresses)).run_batch()

    assert summary.total_jobs == 5
    assert summary.passed == 5
    assert [item.email for item in summary.results] == addresses
    assert len(repository.list_results(summary.run_id)) == 5


def test_batch_rejects_not_exactly_five_addresses(tmp_path):
    repository = SQLiteRepository(tmp_path / "qa.sqlite3")
    with pytest.raises(MailboxError, match="Exactly five"):
        FiveMailboxBatchRunner(
            repository,
            settings(["qa01@teguhharits.com"]),
        ).run_batch()


def test_batch_rejects_addresses_outside_configured_domain(tmp_path):
    repository = SQLiteRepository(tmp_path / "qa.sqlite3")
    addresses = [f"qa0{i}@example.test" for i in range(1, 6)]
    with pytest.raises(MailboxError, match="configured domain"):
        FiveMailboxBatchRunner(repository, settings(addresses)).run_batch()
