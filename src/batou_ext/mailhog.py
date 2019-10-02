import batou.component
import batou.lib.file
import batou_ext.nix
import os.path
import pkg_resources


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
    Mails can be send to the srv address on port 1025.

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

    public_name = None
    public_http = 80
    public_https = 443
    mailport = 1025
    uiport = 8025
    address = None
    ssl_address = None
    address_mail = None
    address_ui = None

    key_content = None
    crt_content = None
    letsencrypt = batou.component.Attribute("literal", True)
    docroot = None

    http_auth_enable = batou.component.Attribute("literal", False)
    http_basic_auth = None

    def configure(self):
        # self.provide('mail', self)

        self.address = batou.utils.Address(self.public_name, self.public_http)
        self.ssl_address = batou.utils.Address(
            self.public_name, self.public_https
        )
        self.address_mail = batou.utils.Address(self.host.fqdn, self.mailport)
        self.address_ui = batou.utils.Address(self.host.fqdn, self.uiport)

        if self.http_auth_enable:
            if self.http_basic_auth is not None:
                self.http_auth = self.http_basic_auth
            else:
                self.http_auth = self.require_one("http_basic_auth")

        self += batou.lib.file.File(
            "mailhog_env",
            content=self.expand(
                """
# File managed by batou. Don't edit manually

MH_HOSTNAME={{component.public_name}}
MH_SMTP_BIND_ADDR={{component.address_mail.listen}}
MH_API_BIND_ADDR={{component.address_ui.listen}}
MH_UI_BIND_ADDR={{component.address_ui.listen}}
"""
            ),
        )
        self.envfile = self._

        self += batou.lib.file.File(
            "mailhog",
            mode=0o755,
            content=self.expand(
                """#!/bin/sh
set -e
NAME={{component.public_name}}

# Not sure we really want this. Only used within dev.
docker pull mailhog/mailhog

docker stop $NAME || true
docker rm $NAME || true

docker run \
--network host \
--name="$NAME" \
--env-file={{component.envfile.path}} \
--mount source=mailhog-vol,dst=/var/lib/mailhog \
mailhog/mailhog
"""
            ),
        )

        # use own nginx config to integrate into frontend, if mailhog is used
        if not self.docroot:
            self.docroot = self.map("htdocs")
        self += batou.lib.file.File(
            self.docroot, ensure="directory", leading=True
        )

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
                __name__, "resources/mailhog/mailhog.conf"
            ),
        )

        self += batou_ext.nix.Rebuild()
        self += self.cert.activate_letsencrypt()

        self += batou.lib.service.Service(
            "mailhog", systemd=dict(Restart="always", Type="simple")
        )
