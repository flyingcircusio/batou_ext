from importlib.resources import files
from textwrap import dedent

import batou.component
import batou.lib.file

import batou_ext.nix
import batou_ext.ssl


@batou_ext.nix.rebuild
class PostfixRelay(batou.component.Component):
    """Relay outpoing mail via another SMTP server.

    This requires the FC mailstub role and proper credentials for the remote
    host.

    """

    _required_params_ = {
        "smtp_relay_host": "smtp",
        "smtp_user": "scott",
        "smtp_password": "tiger",
    }
    smtp_relay_host = batou.component.Attribute(str)
    smtp_relay_port = batou.component.Attribute(int, 587)
    smtp_tls = batou.component.Attribute("literal", "True")

    smtp_auth = batou.component.Attribute("literal", default=True)
    smtp_user = batou.component.Attribute(str)
    smtp_password = batou.component.Attribute(str)

    provide_as = None  # (optional) str to self.provide()

    def configure(self):
        if self.provide_as:
            self.provide(self.provide_as, self)
        self.address = batou.utils.Address(self.host.fqdn, 25, require_v6=True)
        self += batou.lib.file.File(
            "/etc/local/postfix/main.cf",
            content=dedent(
                self.expand(
                    """
    relayhost = [{{component.smtp_relay_host}}]:{{component.smtp_relay_port}}
    {% if component.smtp_auth %}
    smtp_sasl_auth_enable = yes
    smtp_sasl_password_maps = hash:/etc/local/postfix/sasl_passwd
    smtp_sasl_security_options = noanonymous
    {% endif %}
    {% if component.smtp_tls %}smtp_use_tls = yes{% endif %}
    """
                )
            ),
        )

        if self.smtp_auth:
            self += batou.lib.file.File(
                "/etc/local/postfix/sasl_passwd",
                content=(
                    f"[{self.smtp_relay_host}]:{self.smtp_relay_port}"
                    f" {self.smtp_user}:{self.smtp_password}"
                ),
                sensitive_data=True,
            )
        else:
            self += batou.lib.file.Purge("/etc/local/postfix/sasl_passwd")
            self += batou.lib.file.Purge("/etc/local/postfix/sasl_passwd.db")

    def verify(self):
        if self.smtp_auth:
            self.assert_file_is_current(
                "/etc/local/postfix/sasl_passwd.db",
                requirements=["/etc/local/postfix/sasl_passwd"],
            )

    def update(self):
        if self.smtp_auth:
            with self.chdir("/etc/local/postfix"):
                self.cmd("postmap sasl_passwd")


@batou_ext.nix.rebuild
class Mailhog(batou.component.Component):
    """Set up a local testing mail server with mailog.

    This component provides a local dev mail setup.

    Usage:
    Just add mailhog to the enivronment and set `public_name`.
    Mailog will then be availabe under the `public_name` on port 80 and 443.
    You should use a subdomain to avoid conflicts, or change public_http(s).

    Note: Mails can be send to the FQDN of the host mailhog is running
    on. If you need: Connection details are stored inside the
    Address-object of self.address.

    For usage with basic auth you might like to use
    batou_ext.http.HTTPBasicAuth.

    When using the Mailhog component explicitly in one of your components you
    may do so like this::

        self.http_auth = self.require_one("http_basic_auth")
        self += batou_ext.mailhog.Mailhog(
            public_name=self.mail_public_name,
            http_auth_enable=True,
            http_basic_auth=self.http_auth
         )

    This example is adding an explicit batou_ext.http.HTTPBasicAuth
    rather than just pulling it from environment.
    """

    _required_params_ = {
        "public_name": "example.com",
        "public_smtp_name": "mail.flyingcircus.io",
    }
    public_name = batou.component.Attribute(str)
    public_smtp_name = batou.component.Attribute(str, default=None)
    mailport = batou.component.Attribute(int, 1025)
    uiport = batou.component.Attribute(int, 8025)
    apiport = batou.component.Attribute(int, 8025)
    purge_old_mailhog_configs = batou.component.Attribute(
        "literal", default=True
    )
    http_auth_enable = batou.component.Attribute("literal", default=False)
    http_basic_auth = None

    systemd_namespace = batou.component.Attribute(str, default="")
    disable_stdout = batou.component.Attribute("literal", default=False)

    # Either memory or maildir
    # mongodb is not yet supported
    storage_engine = batou.component.Attribute(str, default="memory")

    provide_as = None  # (optional) str to self.provide()

    def configure(self):
        if self.provide_as:
            self.provide(self.provide_as, self)

        if not self.public_smtp_name:
            self.public_smtp_name = self.host.fqdn

        # Migration from old nginx.conf
        if self.purge_old_mailhog_configs:
            self += batou.lib.file.Purge("mailhog")
            self += batou.lib.file.Purge("mailhog_env")
            self += batou.lib.file.Purge("/etc/local/systemd/mailhog.service")
            self += batou.lib.file.Purge("/etc/local/nginx/mailhog.conf")
            self += batou.lib.file.Purge("htdocs")

        self.address = batou.utils.Address(self.public_smtp_name, self.mailport)
        self.address_ui = batou.utils.Address(self.public_name, self.uiport)

        if self.http_auth_enable:
            if self.http_basic_auth is None:
                self.http_auth = self.require_one("http_basic_auth")
            else:
                self.http_auth = self.http_basic_auth

        self += batou.lib.file.File(
            "/etc/local/nixos/mailhog.nix",
            content=(
                files(__spec__.parent) / "resources/mailhog/mailhog.nix"
            ).read_bytes(),
        )


@batou_ext.nix.rebuild
class Mailpit(batou.component.Component):
    _required_params_ = {
        "public_name": "example.com",
    }

    public_name = batou.component.Attribute(str)
    public_smtp_name = batou.component.Attribute(str, default=None)
    ui_port = batou.component.Attribute(int, 8025)
    smtp_port = batou.component.Attribute(int, 1025)

    max = batou.component.Attribute(int, 500)

    http_basic_auth = None

    provide_as = None  # (optional) str to self.provide()

    def configure(self):
        if self.provide_as:
            self.provide(self.provide_as, self)

        if not self.public_smtp_name:
            self.public_smtp_name = self.host.fqdn

        self.address = batou.utils.Address(
            self.public_smtp_name, self.smtp_port
        )

        if self.http_basic_auth is None:
            self.http_auth = self.require_one("http_basic_auth")
        else:
            self.http_auth = self.http_basic_auth

        self += batou.lib.file.File(
            "/etc/local/nixos/mailpit.nix",
            content=(
                files(__spec__.parent) / "resources/mailpit.nix"
            ).read_bytes(),
        )
