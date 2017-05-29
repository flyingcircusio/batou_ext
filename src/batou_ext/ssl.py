import batou.component
import batou.lib.cron
import batou.lib.download
import batou.lib.file
import hashlib
import os
import os.path
import pkg_resources
import tempfile


class Certificate(batou.component.Component):
    """SSL certificate management using let's encrypt -- or not

    Usage:

        # Add certificate component. After this step, a key and certificate
        # is available. In case of Let's Encrypt it's a self-signed one.
        self.cert = Certificate(
            self.public_name,
            docroot=self.docroot,
            key_content=self.key_content,
            crt_content=self.crt_content,
            use_letsencrypt=self.letsencrypt
        )
        self += self.cert

        # Configure web server. Use `key` and `fullchain` attributes to get
        # the paths to the key and the certificate:
        self += batou.lib.file.File(
            '/etc/local/nginx/myconfig.conf')

        # Activate the configuration.
        self += batou_ext.nix.Rebuild()

        # Actually get a proper Let's Encrypt certificate. This step does
        # nothing, if you don't use LE.
        self += self.cert.activate_letsencrypt()

    """

    # Let's Encrypt
    dehydrated_url = (
        "https://raw.githubusercontent.com/lukas2511/dehydrated/"
        "b36d638a910ce7c6be0bb8330d1d945a653f70af/dehydrated")
    dehydrated_checksum = 'md5:5670eedfda142835130a2220641bb582'

    namevar = 'domain'
    domain = None

    wellknown = None
    docroot = None

    refresh_timing = None

    # Optinal if you are having a valid certificate and don't want to
    # make usage of letsencrypt
    key_content = None
    crt_content = None
    use_letsencrypt = batou.component.Attribute('literal', True)

    def configure(self):
        if not self.refresh_timing:
            h = int(hashlib.md5(self.domain).hexdigest(), 16)
            self.refresh_timing = '{} {} * * *'.format(
                h % 60, h % 24)
        if self.key_content and not self.use_letsencrypt:
            self.crt_file = batou.lib.file.File(
                os.path.join('{}/{}.crt'.format(self.workdir, self.domain)),
                content=self.crt_content)
            self += self.crt_file
            self.key_file = batou.lib.file.File(
                os.path.join('{}/{}.key'.format(self.workdir, self.domain)),
                content=self.key_content,
                mode=0o600)
            self += self.key_file

            self.key = self.key_file.path
            self.fullchain = self.crt_file.path

        else:
            # Okay, let's encrypt it is. There are two situations:
            # 1. bootstrap -- there is nothing.
            # 2. there already is a cert, either replace it with
            #    LE or refresh existing LE.

            self += batou.lib.download.Download(
                self.dehydrated_url,
                checksum=self.dehydrated_checksum,
                target='dehydrated')
            self += batou.lib.file.Mode('dehydrated', mode=0o755)

            if not self.wellknown and self.docroot:
                self.wellknown = '{}/.well-known/acme-challenge'.format(
                    self.docroot)
            self += batou.lib.file.File(
                self.wellknown, ensure='directory', leading=True)

            self += batou.lib.file.File(
                'cert-{}.conf'.format(self.domain),
                content='WELLKNOWN={}'.format(self.wellknown))
            self.config = self._

            self += batou.lib.file.File(
                'cert-{}.sh'.format(self.domain),
                content=pkg_resources.resource_string(
                    'batou_ext', 'resources/cert.sh'),
                mode=0o700)
            self.cert_sh = self._

            self += batou.lib.cron.CronJob(
                self.cert_sh.path,
                timing=self.refresh_timing,
                logger='cert-update')

            self.key_dir = os.path.join(self.workdir, self.domain)
            self.key = os.path.join(self.key_dir, 'privkey.pem')
            self.fullchain = os.path.join(self.key_dir, 'fullchain.pem')

    def activate_letsencrypt(self):
        """Return a component which really activates LE"""
        return ActivateLetsEncrypt(cert=self)

    def verify(self):
        if not self.use_letsencrypt:
            return
        if os.path.exists(self.key) and os.path.exists(self.fullchain):
            # So there are certificates. All done.
            return
        raise batou.UpdateNeeded()

    def update(self):
        # Create a temporary, self-signed certificate, to let the web server
        # start up, so let's encrypt can do what it needs.
        os.makedirs(self.key_dir)
        self.csr_file = tempfile.NamedTemporaryFile()
        self.cmd('openssl genrsa -out {{component.key}} 2048')
        self.cmd("""\
openssl req -new \
    -key {{component.key}} \
    -out {{component.csr_file.name}} \
    -batch \
    -subj "/CN={{component.domain}}/emailAddress=admin@{{component.domain}}/C=DE"
""")  # noqa
        self.cmd("""
openssl x509 -req -days 3650 \
    -in {{component.csr_file.name}} \
    -signkey {{component.key}} \
    -out {{component.fullchain}}
""")
        self.csr_file.close()
        del self.csr_file


class ActivateLetsEncrypt(batou.component.Component):

    def verify(self):
        self.cert.assert_no_subcomponent_changes()

    def update(self):
        if self.cert.use_letsencrypt:
            self.cmd(self.cert.cert_sh.path)
