from unittest import mock

import pytest
from batou import UpdateNeeded

from batou_ext import postgres


@pytest.fixture
def grant(root):
    g = postgres.Grant(
        "myuser",
        db="mydb",
        schema="public",
        table_permissions=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )
    g.prepare(root)
    return g


def test_grant_configure_requires_db(root):
    g = postgres.Grant("myuser", schema="public")
    with pytest.raises(ValueError, match="Need to specify db"):
        g.configure()


def test_grant_configure_success(grant):
    assert grant.user == "myuser"
    assert grant.db == "mydb"
    assert grant.schema == "public"
    assert grant.table_permissions == ["SELECT", "INSERT", "UPDATE", "DELETE"]
    assert grant.schema_permissions == ["USAGE"]


def test_grant_default_permissions(root):
    g = postgres.Grant("myuser", db="mydb")
    g.prepare(root)
    assert g.schema == "public"
    assert g.table_permissions == ["SELECT", "INSERT", "UPDATE", "DELETE"]
    assert g.schema_permissions == ["USAGE"]


def test_grant_custom_permissions(root):
    g = postgres.Grant(
        "myuser",
        db="mydb",
        schema="myschema",
        table_permissions=["SELECT"],
        schema_permissions=["USAGE", "CREATE"],
    )
    g.prepare(root)
    assert g.table_permissions == ["SELECT"]
    assert g.schema_permissions == ["USAGE", "CREATE"]


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_verify_no_permissions_raises(pgcmd_mock, grant):
    pgcmd_mock.return_value = ("", "")
    with pytest.raises(UpdateNeeded):
        grant.verify()


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_verify_has_permissions(pgcmd_mock, grant):
    pgcmd_mock.side_effect = [
        ("SELECT\nINSERT\nUPDATE\nDELETE", ""),
        ("USAGE", ""),
    ]
    grant.verify()


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_verify_partial_permissions_raises(pgcmd_mock, grant):
    pgcmd_mock.side_effect = [
        ("SELECT\nINSERT", ""),
        ("USAGE", ""),
    ]
    with pytest.raises(UpdateNeeded):
        grant.verify()


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_update(pgcmd_mock, grant):
    pgcmd_mock.return_value = ("", "")
    grant.update()


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_update_no_tables(pgcmd_mock, grant):
    pgcmd_mock.side_effect = [("", ""), ("", ""), ("", "")]
    grant.update()


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_check_permissions(pgcmd_mock, grant):
    pgcmd_mock.side_effect = [
        ("SELECT\nINSERT\nUPDATE\nDELETE", ""),
        ("USAGE", ""),
    ]
    result = grant._check_permissions()
    assert result == []


@mock.patch.object(postgres.Grant, "pgcmd")
def test_grant_check_permissions_missing(pgcmd_mock, grant):
    pgcmd_mock.side_effect = [
        ("SELECT", ""),
        ("", ""),
    ]
    result = grant._check_permissions()
    assert "table permissions" in result[0]
    assert "INSERT" in result[0] or "UPDATE" in result[0] or "DELETE" in result[0]
