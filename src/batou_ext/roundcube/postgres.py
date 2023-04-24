from batou.component import Component

from batou_ext.postgres import DB, User


class RoundcubeDatabase(Component):

    _required_params_ = {
        "password": "tiger",
    }
    username = "roundcube"
    password = None
    database = "roundcube"

    dbms = "pgsql"

    command_prefix = ""
    locale = "en_US.utf8"

    def configure(self):
        dbserver = self.require_one("postgres")
        self.address = dbserver.address
        self.provide("roundcube::database", self)
        self += User(self.username, password=self.password)
        self += DB(self.database, owner=self.username, locale=self.locale)
