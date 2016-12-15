import batou.component
import batou.lib.cron
import batou.lib.download
import batou.lib.file
import pkg_resources

class Certificate(batou.component.Component):

    dehydrated_url = (
        "https://github.com/lukas2511/dehydrated/raw/"
        "ec49a4433b48a7bc8f178d06dad3f55cff24bdf3/dehydrated")
    dehydrated_checksum = 'md5:8e47a8cefe010f627ec2831952995606'

    domain = None

    wellknown = None
    docroot = None

    # TODO: make depend on domainname
    refresh_timing = '24 9 * * *'

    def configure(self):
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
        self.cmd(self.cert_sh.path)
