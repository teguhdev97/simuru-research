from __future__ import annotations

from simuru_research.storage.team_accounts import TeamAccountRegistry


def test_add_personal_account_is_manual_only(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")

    inserted = registry.add_account(
        username="team.personal_01",
        owner_label="QA Team",
        account_type="personal",
        owner_approved=True,
        notes="Existing team account",
    )

    assert inserted is True
    account = registry.list_accounts()[0]
    assert account["username"] == "team.personal_01"
    assert account["api_status"] == "manual_only"
    assert account["owner_approved"] == 1


def test_professional_account_waits_for_meta_oauth(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")

    registry.add_account(
        username="team.creator_01",
        owner_label="Content Team",
        account_type="creator",
        owner_approved=True,
    )

    account = registry.list_accounts()[0]
    assert account["api_status"] == "pending_meta_oauth"


def test_duplicate_username_is_not_inserted_twice(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")
    values = {
        "username": "Team.Account",
        "owner_label": "QA",
        "account_type": "personal",
        "owner_approved": True,
    }

    assert registry.add_account(**values) is True
    assert registry.add_account(**values) is False
    assert len(registry.list_accounts()) == 1


def test_requires_owner_authorization_and_valid_username(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")

    try:
        registry.add_account(
            username="team_account",
            owner_label="QA",
            account_type="personal",
            owner_approved=False,
        )
    except ValueError as exc:
        assert "authorization" in str(exc)
    else:
        raise AssertionError("Expected owner authorization validation.")

    try:
        registry.add_account(
            username="invalid username",
            owner_label="QA",
            account_type="personal",
            owner_approved=True,
        )
    except ValueError as exc:
        assert "Username" in str(exc)
    else:
        raise AssertionError("Expected username validation.")


def test_import_csv_requires_confirmation_and_skips_unapproved_rows(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")
    csv_content = (
        "username,owner_label,account_type,owner_approved,notes\n"
        "team.one,QA,personal,true,Approved\n"
        "team.two,QA,personal,false,Not approved\n"
    )

    try:
        registry.import_csv(csv_content, confirmed=False)
    except ValueError as exc:
        assert "Confirm" in str(exc)
    else:
        raise AssertionError("Expected import confirmation validation.")

    result = registry.import_csv(csv_content, confirmed=True)

    assert result == {
        "imported": 1,
        "duplicates": 0,
        "unauthorized": 1,
        "invalid": 0,
    }
    assert len(registry.list_accounts()) == 1


def test_export_contains_metadata_only(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")
    registry.add_account(
        username="team.safe",
        owner_label="QA",
        account_type="business",
        owner_approved=True,
    )

    exported = registry.export_csv()

    assert "username,owner_label,account_type,owner_approved,notes" in exported
    assert "password" not in exported.lower()
    assert "otp" not in exported.lower()
    assert "access_token" not in exported.lower()


def test_counts_by_account_type(tmp_path) -> None:
    registry = TeamAccountRegistry(tmp_path / "team.sqlite3")
    registry.add_account(
        username="team.personal",
        owner_label="QA",
        account_type="personal",
        owner_approved=True,
    )
    registry.add_account(
        username="team.creator",
        owner_label="Content",
        account_type="creator",
        owner_approved=True,
    )

    assert registry.count_by_type() == {
        "business": 0,
        "creator": 1,
        "personal": 1,
    }
