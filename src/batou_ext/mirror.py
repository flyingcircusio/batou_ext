import os.path

import batou.component
import batou.lib.file

import batou_ext.nix
import batou_ext.ssl


@batou_ext.nix.rebuild
class Mirror(batou.component.Component):
    """Provide a package download mirror (server), and access to it (client).

    Usage: Server::

        [component:mirror]
        nginx_enable = True
        authstring = htpasswd-compatible file format
        nginx_config_path = /etc/local/nginx
        public_name = packages.example.com

    Usage: Client::

        [component:mirror]
        credentials = username:password
        public_name = packages.example.com


    Usage in components::

        mirror = self.require_one('mirror')
        self += Download(mirror.url('/path/to/package'))


    Server and client can be folded into one, when defining the options
    required for both in the same component.

    """

    public_name = None
    base = batou.component.Attribute(
        str, default="{protocol}://{credentials}@{public_name}"
    )
    protocol = batou.component.Attribute(str, default="https")

    # Whether Nginx-configuration should be provided
    nginx_enable = batou.component.Attribute("literal", default=False)
    nginx_config_path = None
    nginx_docroot = None

    # Define non-default reload command for Nginx used e.g. on renewal
    # of SSL-certificate if possible
    nginx_reload_command = batou.component.Attribute(
        str, default="sudo systemctl reload nginx"
    )

    provide_itself = batou.component.Attribute("literal", default=True)

    credentials = None
    authstring = None

    # Whether we shall run let's encrypt for Nginx configuration
    # If set to 'False', a self-signed certificate will be deployed instead
    use_letsencrypt = batou.component.Attribute("literal", default=True)

    def configure(self):

        if self.provide_itself:
            self.provide("mirror", self)

        if self.nginx_enable:
            self.nginx_enable_config()

    def url(self, path):
        return (
            self.base.format(
                protocol=self.protocol,
                credentials=self.credentials,
                public_name=self.public_name,
            )
            + "/"
            + path
        )

    def nginx_enable_config(self):
        self.address = batou.utils.Address(self.public_name, 80)
        self.ssl_address = batou.utils.Address(self.public_name, 443)

        if not self.nginx_docroot:
            self.nginx_docroot = self.map("htdocs")

        self += batou.lib.file.File(self.nginx_docroot, ensure="directory")

        self.cert = batou_ext.ssl.Certificate(
            self.public_name,
            docroot=self.nginx_docroot,
            extracommand=self.nginx_reload_command,
            use_letsencrypt=self.use_letsencrypt,
        )
        self += self.cert

        if self.authstring:
            self.htpasswdfile = batou.lib.file.File(
                "htpasswd", content=self.authstring
            )
            self += self.htpasswdfile

        assert self.nginx_config_path

        self += batou.lib.file.File(
            "{}/{}.conf".format(self.nginx_config_path, self.public_name),
            source=os.path.join(
                os.path.dirname(__file__), "resources/mirror.conf"
            ),
        )

        self += self.cert.activate_letsencrypt()
