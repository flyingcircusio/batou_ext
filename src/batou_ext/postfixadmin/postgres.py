from batou.component import Component, Attribute
from batou.utils import Address
from batou_ext.postgres import DB, User


class PFADatabase(Component):

    username = 'postfix'
    password = None
    database = 'postfix'

    dbms = 'pgsql'

    command_prefix = 'sudo -u postgres'
    locale = 'en_US.UTF-8'

    def configure(self):
        dbserver = self.require_one('postgres')
        self.address = dbserver.address
        self.provide('pfa::database', self)
        self += User(self.username, password=self.password)
        self += DB(self.database, owner=self.username, locale=self.locale)
