import batou.component
import batou.lib.file
import batou_ext.nix
import os.path
import pkg_resources


class Mailhog(batou.component.Component):
    """
    This component provides a local dev mail setup.
    You need to activate docker role, nginx and a frontend IP for the UI
    to be accessible.

    Usage:
    Just add mailhog to the enivronment and overwrite needed public_name.
    Mailog will then be availabe under public_name on port 80 and 443,
    so you should use a subdomain to avoid conflicts or overwrite
    public_http(s).
    Mails can be send to srv address on port 1025.
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

    def configure(self):
        # self.provide('mail', self)

        self.address = batou.utils.Address(self.public_name, self.public_http)
        self.ssl_address = batou.utils.Address(self.public_name, self.public_https)
        self.address_mail = batou.utils.Address(self.host.fqdn, self.mailport)
        self.address_ui = batou.utils.Address(self.host.fqdn, self.uiport)

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
        self += batou.lib.file.File(self.docroot, ensure="directory", leading=True)

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
