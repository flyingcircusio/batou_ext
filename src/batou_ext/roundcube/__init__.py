import os

from batou import UpdateNeeded
from batou.component import Attribute, Component, ConfigString
from batou.lib.archive import Extract
from batou.lib.download import Download
from batou.lib.file import Directory, File, SyncDirectory
from batou.utils import Address

from batou_ext.php import FPM


class Roundcube(Component):
    """Configure Roundcube with database connection.

    Roundcube is installed with php/fastcgi. A basic configuration for the
    frontend is created but it is up to the user to fine-tune that
    configuration.
    """

    release = "1.1.4"
    checksum = "sha256:9bfe88255d4ffc288f5776de1cead78352469b1766d5ebaebe6e28043affe181"  # noqa: E501 line too long

    address = Attribute(Address, ConfigString("127.0.0.1:9000"))
    skin = "larry"
    support_url = "http://localhost"

    smtp_user = "%u"
    smtp_pass = "%p"

    config = os.path.join(os.path.dirname(__file__), "config.inc.php")

    def configure(self):
        self.db = self.require_one("roundcube::database")
        postfix = self.require_one("postfix")

        self.imap_host = postfix.connect.host
        self.smtp_server = postfix.connect.host
        self.smtp_port = postfix.connect.port

        self.basedir = self.map("roundcube")
        self.provide("roundcube", self)

        self += Directory("download")
        download = Download(
            "http://downloads.sourceforge.net/project/roundcubemail/"
            "roundcubemail/{}/roundcubemail-{}-complete.tar.gz".format(
                self.release, self.release
            ),
            target="download/roundcube-{}.tar.gz".format(self.release),
            checksum=self.checksum,
        )
        self += download

        self += Extract(download.target, target="roundcube.orig")
        self += SyncDirectory(
            self.basedir,
            source=self.map(
                "roundcube.orig/roundcubemail-{}".format(self.release)
            ),
        )

        self.db_dsnw = "{}://{}:{}@{}/{}".format(
            self.db.dbms,
            self.db.username,
            self.db.password,
            self.db.address.connect.host,
            self.db.database,
        )

        self += File(
            self.basedir + "/config/config.inc.php", source=self.config
        )

        self.fpm = FPM("roundcube")
        self += self.fpm

        self += RoundcubeInit(self)


class RoundcubeInit(Component):

    namevar = "roundcube"

    def verify(self):
        os.environ["PGPASSWORD"] = self.roundcube.db.password
        host = self.roundcube.db.address.connect.host
        db = self.roundcube.db
        try:

            result = self.cmd(
                f"psql -h {host} -U {db.username} -d {db.database} -c "
                '"SELECT * FROM information_schema.tables '
                "WHERE table_schema='public' "
                "AND table_catalog='roundcube';\""
            )
            if "contact" not in result[0]:
                raise UpdateNeeded()
        finally:
            del os.environ["PGPASSWORD"]

    def update(self):
        os.environ["PGPASSWORD"] = self.roundcube.db.password
        self.cmd(
            "psql -h {} -d {} -U {} -f {}/SQL/postgres.initial.sql".format(
                self.roundcube.db.address.connect.host,
                self.roundcube.db.database,
                self.roundcube.db.username,
                self.roundcube.basedir,
            )
        )
        del os.environ["PGPASSWORD"]
