from batou.component import Component, Attribute
from batou.lib.archive import Extract
from batou.lib.download import Download
from batou.lib.file import File, SyncDirectory
from batou.lib.nagios import ServiceCheck
from batou.lib.supervisor import Program
from batou.utils import Address
from batou_ext.fpm import FPM
import hashlib
import os

class PFA(Component):

    release = '2.92'
    checksum = 'sha1:21481f6eb8f10ba05fc6fcd1fe0fd468062956f2'

    address = Attribute(Address, '127.0.0.1:9001')

    admin_password = None
    salt = 'ab8f1b639d31875b59fa047481c581fd'
    config = os.path.join(
        os.path.dirname(__file__),
        'postfixadmin',
        'config.local.php')

    def configure(self):
        self.db = self.require_one('pfa::database')
        self.postfix = self.require_one('postfix')
#        self.provide('pfa', self)

        self.basedir = self.map('postfixadmin')

        download = Download(
            'http://downloads.sourceforge.net/project/postfixadmin/'
            'postfixadmin/postfixadmin-{}/postfixadmin-{}.tar.gz'.format(
                self.release, self.release),
            target='postfixadmin-{}.tar.gz'.format(self.release),
            checksum=self.checksum)
        self += download
        self += Extract(download.target, target='postfixadmin.orig')

        self += SyncDirectory(
            self.basedir,
            source=self.map(
                'postfixadmin.orig/postfixadmin-{}'.format(self.release)))

        self += File(self.basedir + '/config.local.php', source=self.config)

        self += FPM('postfixadmin', adress=self.address)

    @property
    def admin_password_encrypted(self):
        # password generation ported from postfixadmin/setup.php

        encrypt = hashlib.sha1()
        encrypt.update("{}:{}".format(self.salt, self.admin_password))

        return "{}:{}".format(self.salt, encrypt.hexdigest())
