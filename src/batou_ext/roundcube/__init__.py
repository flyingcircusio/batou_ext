from batou.component import Component, Attribute
from batou.lib.archive import Extract
from batou.lib.download import Download
from batou.lib.file import Directory, File, SyncDirectory
from batou.utils import Address
from batou_ext.fpm import FPM
import os


class Roundcube(Component):
    """Configure Roundcube with database connection.

    Roundcube is installed with php/fastcgi. A basic configuration for the
    frontend is created but it is up to the user to fine-tune that
    configuration.
    """

    release = '1.1.1'
    checksum = 'sha1:a53a2d17bce9c382bc7b62bb76d2dce94d55b1f8'

    address = Attribute(Address, '127.0.0.1:9000')

    smtp_user = '%u'
    smtp_pass = '%p'

    config = os.path.join(os.path.dirname(__file__), 'config.inc.php')

    def configure(self):
        self.db = self.require_one('roundcube::database')
        postfix = self.require_one('postfix')

        self.imap_host = postfix.connect.host
        self.smtp_server = postfix.connect.host
        self.smtp_port = postfix.connect.port

        self.basedir = self.map('roundcube')
        self.provide('roundcube', self)

        self += Directory('download')
        download = Download(
            'http://downloads.sourceforge.net/project/roundcubemail/'
            'roundcubemail/{}/roundcubemail-{}-complete.tar.gz'.format(
                self.release, self.release),
            target='download/roundcube-{}.tar.gz'.format(self.release),
            checksum=self.checksum)
        self += download

        self += Extract(download.target, target='roundcube.orig')
        self += SyncDirectory(
            self.basedir,
            source=self.map(
                'roundcube.orig/roundcubemail-{}'.format(self.release)))

        self.db_dsnw = '{}://{}:{}@{}/{}'.format(
            self.db.dbms,
            self.db.username,
            self.db.password,
            self.db.address.connect.host,
            self.db.database)

        self += File(
            self.basedir + '/config/config.inc.php',
            source=self.config)

        self.fpm = FPM('roundcube', address=self.address)
        self += self.fpm
