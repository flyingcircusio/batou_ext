from .mail import Mailhog


class Mailhog(Mailhog):
    """(deprecated) BW compatibility for .mail.Mailhog."""

    # Either memory or maildir
    # mongodb is not yet supported here
    storage_engine = batou.component.Attribute(str, default='memory')

    def configure(self):
        super().configure()
        self.address_mail = self.address
        self.address = self.address_http
