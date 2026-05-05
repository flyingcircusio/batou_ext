import pytest

from batou_ext.mail import PostfixRelay


def _get_nix_content(relay):
    return relay.sub_components[0].content.decode()


@pytest.fixture
def relay(root):
    r = PostfixRelay(
        smtp_relay_host="smtp.example.com",
        smtp_user="scott",
        smtp_password="tiger",
    )
    r.prepare(root)
    return r


def test_relay_host_without_brackets(relay):
    assert relay.smtp_relay_host == "smtp.example.com"


def test_nix_config_contains_bracketed_relayhost(relay):
    content = _get_nix_content(relay)
    assert '"[smtp.example.com]:587"' in content


def test_nix_config_contains_smtp_tls_security_level(relay):
    content = _get_nix_content(relay)
    assert 'smtp_tls_security_level = "encrypt"' in content
    assert "smtp_use_tls" not in content


def test_nix_config_no_tls_when_disabled(root):
    r = PostfixRelay(
        smtp_relay_host="smtp.example.com",
        smtp_user="scott",
        smtp_password="tiger",
    )
    r.smtp_tls = False
    r.prepare(root)
    content = _get_nix_content(r)
    assert "smtp_tls_security_level" not in content


def test_nix_config_my_networks_empty_by_default(relay):
    content = _get_nix_content(relay)
    assert "mynetworks" not in content


def test_nix_config_my_networks_set(root):
    r = PostfixRelay(
        smtp_relay_host="smtp.example.com",
        smtp_user="scott",
        smtp_password="tiger",
        my_networks=["10.0.0.0/8", "172.16.0.0/12"],
    )
    r.prepare(root)
    content = _get_nix_content(r)
    assert "10.0.0.0/8" in content
    assert "172.16.0.0/12" in content


def test_nix_config_no_auth_skips_sasl(relay):
    content = _get_nix_content(relay)
    assert "smtp_sasl_auth_enable" in content


def test_nix_config_no_auth_when_disabled(root):
    r = PostfixRelay(
        smtp_relay_host="smtp.example.com",
        smtp_user="scott",
        smtp_password="tiger",
    )
    r.smtp_auth = False
    r.prepare(root)
    content = _get_nix_content(r)
    assert "smtp_sasl_auth_enable" not in content
