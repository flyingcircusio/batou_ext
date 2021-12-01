from textwrap import dedent

import batou.component
import batou.lib.file
import pkg_resources

import batou_ext.nix
import batou_ext.ssl


@batou_ext.nix.rebuild
class PostfixRelay(batou.component.Component):
    """Relay outpoing mail via another SMTP server.

    This requires the FC mailstub role and proper credentials for the remote
    host.

    """

    _required_params_ = {
        'smtp_relay_host': 'smtp',
        'smtp_user': 'scott',
        'smtp_password': 'tiger', }
    smtp_relay_host = batou.component.Attribute(str, default='')
    smtp_relay_port = batou.component.Attribute(int, default=587)
    smtp_tls = batou.component.Attribute("literal", default=True)

    smtp_auth = batou.component.Attribute("literal", default=True)
    smtp_user = batou.component.Attribute(str)
    smtp_password = batou.component.Attribute(str)

    provide_as = None  # (optional) str to self.provide()

    def configure(self):
        if self.provide_as:
            self.provide(self.provide_as, self)
        self.address = batou.utils.Address(self.host.fqdn, 25)
        self += batou.lib.file.File(
            '/etc/local/postfix/main.cf',
            content=dedent(
                self.expand("""
    relayhost = [{{component.smtp_relay_host}}]:{{component.smtp_relay_port}}
    {% if component.smtp_auth %}
    smtp_sasl_auth_enable = yes
    smtp_sasl_password_maps = hash:/etc/local/postfix/sasl_passwd
    smtp_sasl_security_options = noanonymous
    {% endif %}
    {% if component.smtp_tls %}smtp_use_tls = yes{% endif %}
    """)))

        if self.smtp_auth:
            self += batou.lib.file.File(
                '/etc/local/postfix/sasl_passwd',
                content=(f"[{self.smtp_relay_host}]:{self.smtp_relay_port}"
                         f" {self.smtp_user}:{self.smtp_password}"),
                sensitive_data=True)
        else:
            self += batou.lib.file.Purge('/etc/local/postfix/sasl_passwd')
            self += batou.lib.file.Purge('/etc/local/postfix/sasl_passwd.db')

    def verify(self):
        if self.smtp_auth:
            self.assert_file_is_current(
                '/etc/local/postfix/sasl_passwd.db',
                requirements=['/etc/local/postfix/sasl_passwd'])

    def update(self):
        if self.smtp_auth:
            with self.chdir('/etc/local/postfix'):
                self.cmd('postmap sasl_passwd')


@batou_ext.nix.rebuild
class Mailhog(batou.component.Component):
    """Set up a local testing mail server with mailog.

    This component provides a local dev mail setup.
    You need to activate docker role, nginx and a frontend IP for the UI
    to be accessible.

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
        'public_name': 'example.com',
        'public_smtp_name': 'mail.flyingcircus.io', }
    public_name = None
    public_smtp_name = None
    public_http = 80
    public_https = 443
    mailport = 1025
    uiport = 8025

    key_content = None
    crt_content = None
    letsencrypt = batou.component.Attribute("literal", default=True)
    docroot = None

    http_auth_enable = batou.component.Attribute("literal", default=False)
    http_basic_auth = None

    provide_as = None  # (optional) str to self.provide()

    def configure(self):
        if self.provide_as:
            self.provide(self.provide_as, self)

        self.address_http = batou.utils.Address(self.public_name,
                                                self.public_http)
        self.address_ssl = batou.utils.Address(self.public_name,
                                               self.public_https)

        hostname = self.public_smtp_name or self.host.fqdn
        self.address = batou.utils.Address(hostname, self.mailport)
        self.address_ui = batou.utils.Address(self.host.fqdn, self.uiport)

        if self.http_auth_enable:
            if self.http_basic_auth is None:
                self.http_auth = self.require_one("http_basic_auth")
            else:
                self.http_auth = self.http_basic_auth

        self += batou.lib.file.File(
            "mailhog_env",
            content=dedent(
                self.expand("""
                # File managed by batou. Don't edit manually

                MH_HOSTNAME={{component.public_name}}
                MH_SMTP_BIND_ADDR={{component.address.listen}}
                MH_API_BIND_ADDR={{component.address_ui.listen}}
                MH_UI_BIND_ADDR={{component.address_ui.listen}}
                """)))
        self.envfile = self._

        self += batou.lib.file.File(
            "mailhog",
            mode=0o755,
            content=dedent(f"""\
                #!/bin/sh
                set -e
                NAME={self.public_name}

                # Not sure we really want this. Only used within dev.
                docker pull mailhog/mailhog

                docker stop $NAME || true
                docker rm $NAME || true

                docker run \\
                    --network host \\
                    --name="$NAME" \\
                    --env-file={self.envfile.path} \\
                    --mount source=mailhog-vol,dst=/var/lib/mailhog \\
                mailhog/mailhog
                """))

        # use own nginx config to integrate into frontend, if mailhog is used
        if not self.docroot:
            self.docroot = self.map("htdocs")
        self += batou.lib.file.File(
            self.docroot, ensure="directory", leading=True)

        self.cert = batou_ext.ssl.Certificate(
            self.public_name,
            docroot=self.docroot,
            key_content=self.key_content,
            crt_content=self.crt_content,
            use_letsencrypt=self.letsencrypt,
            extracommand="sudo systemctl reload nginx",
        )
        self += self.cert

        self += batou.lib.file.File(
            "/etc/local/nginx/mailhog.conf",
            content=pkg_resources.resource_string(
                __name__, "resources/mailhog/mailhog.conf"),
        )

        self += batou_ext.nix.Rebuild()
        self += self.cert.activate_letsencrypt()

        self += batou.lib.service.Service(
            "mailhog", systemd=dict(Restart="always", Type="simple"))
