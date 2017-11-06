import batou.component
import batou.lib.file
import batou_ext.ssl
import batou_ext.nix
import os.path


@batou_ext.nix.rebuild
class Mirror(batou.component.Component):

    public_name = None
    base = batou.component.Attribute(
        str, '{protocol}://{credentials}@{public_name}')
    protocol = batou.component.Attribute(str, 'https')

    # Whether Nginx-configuration should be provided
    nginx_enable = batou.component.Attribute('literal', False)
    nginx_config_path = None
    nginx_docroot = None

    provide_itself = batou.component.Attribute('literal', True)

    credentials = None
    authstring = None

    def configure(self):

        if self.provide_itself:
            self.provide('mirror', self)

        if self.nginx_enable:
            self.nginx_enable_config()

    def url(self, path):
        return self.base.format(
            protocol=self.protocol,
            credentials=self.credentials,
            public_name=self.public_name) + '/' + path

    def nginx_enable_config(self):
        self.address = batou.utils.Address(self.public_name, 80)
        self.ssl_address = batou.utils.Address(self.public_name, 443)

        if not self.nginx_docroot:
            self.nginx_docroot = self.map('htdocs')

        self += batou.lib.file.File(
            self.nginx_docroot,
            ensure='directory')

        self.cert = batou_ext.ssl.Certificate(
            self.public_name,
            docroot=self.nginx_docroot
        )
        self += self.cert

        if self.authstring:
            self.htpasswdfile = batou.lib.file.File(
                'htpasswd',
                content=self.authstring)
            self += self.htpasswdfile

        assert(self.nginx_config_path)

        self += batou.lib.file.File(
            '{}/{}.conf'.format(
                self.nginx_config_path,
                self.public_name
            ),
            source=os.path.join(
                os.path.dirname(__file__),
                'resources/mirror.conf')
        )

        self += self.cert.activate_letsencrypt()
