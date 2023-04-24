import os

from batou.component import Component
from batou.lib.file import File


class PFADovecot(Component):

    local_conf = os.path.join(
        os.path.dirname(__file__), "dovecot", "local.conf"
    )
    database_conf = os.path.join(
        os.path.dirname(__file__), "dovecot", "database.conf"
    )

    def configure(self):
        self.db = self.require_one("pfa::database")
        self.keypair = self.require_one("keypair::mail")

        self += File("/etc/dovecot/local.conf", source=self.local_conf)
        self += File("database.conf", source=self.database_conf)
