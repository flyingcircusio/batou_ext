from batou.component import Component

from batou_ext.postgres import DB, User


class PFADatabase(Component):

    _required_params_ = {
        "password": "tiger",
    }
    username = "postfix"
    password = None
    database = "postfix"

    dbms = "pgsql"

    command_prefix = ""
    locale = "en_US.utf8"

    def configure(self):
        dbserver = self.require_one("postgres")
        self.address = dbserver.address
        self.provide("pfa::database", self)
        self += User(self.username, password=self.password)
        self += DB(self.database, owner=self.username, locale=self.locale)
