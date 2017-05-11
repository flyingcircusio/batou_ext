import batou.component
import batou.lib.cron
import batou.lib.download
import batou.lib.file
import pkg_resources
import os.path


class Certificate(batou.component.Component):

    # Let's Encrypt
    dehydrated_url = (
        "https://raw.githubusercontent.com/lukas2511/dehydrated/"
        "b36d638a910ce7c6be0bb8330d1d945a653f70af/dehydrated")
    dehydrated_checksum = 'md5:5670eedfda142835130a2220641bb582'

    namevar = 'domain'
    domain = None

    wellknown = None
    docroot = None

    # TODO: make depend on domainname
    refresh_timing = '24 9 * * *'

    # Optinal if you are having a valid certificate and don't want to
    # make usage of letsencrypt
    key_content = None
    crt_content = None
    use_letsencrypt = batou.component.Attribute('literal', True)

    def configure(self):
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

            self.key = "{}/{}/privkey.pem".format(self.workdir, self.domain)
            self.fullchain = "{}/{}/fullchain.pem".format(self.workdir,
                                                          self.domain)

    def verify(self):
        self.assert_no_subcomponent_changes()

    def update(self):
        if self.use_letsencrypt:
            self.cmd(self.cert_sh.path)
