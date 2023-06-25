from .mail import Mailhog


class Mailhog(Mailhog):
    """(deprecated) BW compatibility for .mail.Mailhog."""

    def configure(self):
        super().configure()
        self.address_mail = self.address
        self.address = self.address_ui
