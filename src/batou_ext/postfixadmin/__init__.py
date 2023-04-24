import hashlib
import os

from batou.component import Attribute, Component, ConfigString
from batou.lib.archive import Extract
from batou.lib.download import Download
from batou.lib.file import File, SyncDirectory
from batou.utils import Address

from batou_ext.php import FPM


class PFA(Component):

    _required_params_ = {
        "admin_password": "tiger",
    }
    release = "2.92"
    checksum = "sha1:21481f6eb8f10ba05fc6fcd1fe0fd468062956f2"

    address = Attribute(Address, ConfigString("127.0.0.1:9001"))

    admin_password = None
    salt = "ab8f1b639d31875b59fa047481c581fd"
    config = os.path.join(
        os.path.dirname(__file__), "postfixadmin", "config.local.php"
    )

    def configure(self):
        self.db = self.require_one("pfa::database")
        self.postfix = self.require_one("postfix")
        self.provide("pfa", self)

        self.basedir = self.map("postfixadmin")

        download = Download(
            "http://downloads.sourceforge.net/project/postfixadmin/"
            "postfixadmin/postfixadmin-{}/postfixadmin-{}.tar.gz".format(
                self.release, self.release
            ),
            target="postfixadmin-{}.tar.gz".format(self.release),
            checksum=self.checksum,
        )
        self += download
        self += Extract(download.target, target="postfixadmin.orig")

        self += SyncDirectory(
            self.basedir,
            source=self.map(
                "postfixadmin.orig/postfixadmin-{}".format(self.release)
            ),
        )

        self += File(self.basedir + "/config.local.php", source=self.config)

        self.fpm = FPM("postfixadmin")
        self += self.fpm

    @property
    def admin_password_encrypted(self):
        # password generation ported from postfixadmin/setup.php
        encrypt = hashlib.sha1()
        encrypt.update(
            "{}:{}".format(self.salt, self.admin_password).encode("utf-8")
        )

        return "{}:{}".format(self.salt, encrypt.hexdigest())
