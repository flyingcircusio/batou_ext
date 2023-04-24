import batou.component
import batou.lib.mysql


class MySQLGeneric(batou.component.Component):
    """
    Allows to create default database as used e.g. for typical LAMP-projects

    Usage:
    self += batou_ext.mysql.MySQLGeneric(
        'mydb',
        username='myuser',
        password='mypasswod',
        admin_password='myadminpassword',
        allow_from_hostname='127.0.0.1',
        provide_as='myapplicationdatabase')
    """

    _required_params_ = {
        "username": "scott",
    }
    namevar = "database"
    username = None
    password = None
    admin_password = None

    provide_as = batou.component.Attribute(str, default="mysql")

    port = batou.component.Attribute(int, default=3306)

    # Used for GRANT-string
    allow_from_hostname = batou.component.Attribute(str, default="localhost")

    def configure(self):
        self.provide(self.provide_as, self)

        self.address = batou.utils.Address(self.host.fqdn, self.port)

        self += batou.lib.mysql.Database(
            self.database, admin_password=self.admin_password
        )
        self += batou.lib.mysql.User(
            self.username,
            password=self.password,
            admin_password=self.admin_password,
            allow_from_hostname=self.allow_from_hostname,
        )
        self += batou.lib.mysql.Grant(
            self.database,
            user=self.username,
            admin_password=self.admin_password,
            allow_from_hostname=self.allow_from_hostname,
        )
