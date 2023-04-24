import os

import batou
import batou.component
import batou.utils


class PostgresServer(batou.component.Component):

    listen_port = "5432"

    def configure(self):
        self.address = batou.utils.Address(self.host.fqdn, self.listen_port)
        self.provide("postgres", self)


class PostgresDataComponent(batou.component.Component):

    command_prefix = batou.component.Attribute(str, default="sudo -u postgres")

    def configure(self):
        try:
            self._command_prefix = self.parent.command_prefix
            self.log(
                "{}: Warning: The usage of command_prefix from parent-"
                "component will be deprecated in future. Please update "
                "your deployment to make usage of {}.command_prefix "
                "rather than defining it via {}.command_prefix.".format(
                    self._breadcrumbs,
                    self.__class__.__name__,
                    self.parent.__class__.__name__,
                )
            )
        except AttributeError:
            self._command_prefix = self.command_prefix

    def pgcmd(self, cmd, *args, **kw):
        return self.cmd("{} {}".format(self.command_prefix, cmd), *args, **kw)


class DB(PostgresDataComponent):
    """
    Ensures a given database is created and owned by a specific role.

    Usage:
    self += batou_ext.postgres.DB(
        "mydatabase",
        owner="myuser")

    Attention: The user will not be created automatically.
    """

    _required_params_ = {
        "owner": "scott",
    }
    namevar = "db"
    locale = "en_US.UTF-8"
    template = "template1"
    owner = None

    def configure(self):
        super(DB, self).configure()
        if self.owner is None:
            raise ValueError(
                "You have to specify an owner for the "
                'database "{}"'.format(self.db)
            )

    def verify(self):
        try:
            self.pgcmd(
                self.expand('psql -c "SELECT true;" -d "{{component.db}}"'),
                silent=True,
            )
        except batou.utils.CmdExecutionError:
            raise batou.UpdateNeeded()

    def update(self):
        self.pgcmd(
            self.expand(
                "createdb -T {{component.template}} -l {{component.locale}} -O"
                ' "{{component.owner}}" "{{component.db}}"'
            )
        )


class User(PostgresDataComponent):
    """
    Creates a user/role at the database cluster with a given password
    and flags.

    Usage:
    self += batou_ext.postgres.User(
        "crocodile",
        password="aligator3")
    """

    _required_params_ = {
        "password": "tiger",
    }
    namevar = "name"
    flags = "NOCREATEDB NOCREATEROLE NOSUPERUSER"
    password: str = None

    def configure(self):
        super(User, self).configure()
        assert self.password is not None, "Password for %s is None" % self.name

    def verify(self):
        os.environ["PGPASSWORD"] = self.password
        try:
            self.cmd(
                self.expand(
                    'psql -d postgres -c "SELECT true;" -U'
                    ' "{{component.name}}" -w -h localhost'
                )
            )
        except batou.utils.CmdExecutionError:
            raise batou.UpdateNeeded()
        finally:
            del os.environ["PGPASSWORD"]

    def update(self):
        try:
            command = self.expand(
                'psql -d postgres -c "CREATE USER \\"{{component.name}}\\" PASSWORD \'{{component.password}}\' {{component.flags}}"'  # noqa: E501 line too long
            )
            self.pgcmd(command)
        except batou.utils.CmdExecutionError as e:
            if "already exists" in e.stderr:
                command = self.expand(
                    'psql -d postgres -c "ALTER ROLE \\"{{component.name}}\\" WITH ENCRYPTED PASSWORD \'{{component.password}}\' "'  # noqa: E501 line too long
                )
                self.pgcmd(command)
            else:
                raise e


class Extension(PostgresDataComponent):
    """
    Creates an extension to a given PostgreSQL-DB.

    Usage:
    self += batou_ext.postgres.Extension(
        'uuid-ossp',
        db='my_database')

    Please note: The extension needs to be already present in context
    of the database cluster.
    """

    _required_params_ = {
        "db": "scott",
    }
    namevar = "extension_name"
    db = None

    def configure(self):
        if self.extension_name is None:
            raise ValueError("Need to set extension name")
        if self.db is None:
            raise ValueError(
                "Need to specify a database to " "create extension in"
            )

    def verify(self):
        cmd_out, cmt_err = self.pgcmd(
            self.expand(
                "psql -d {{component.db}} -qtAX "
                '-c "SELECT extname FROM pg_extension '
                "WHERE extname = '{{component.extension_name}}';\""
            )
        )
        if cmd_out.strip() != self.extension_name:
            raise batou.UpdateNeeded()

    def update(self):
        self.pgcmd(
            self.expand(
                "psql -c "
                '"CREATE EXTENSION '
                '\\"{{component.extension_name}}\\";" -d {{component.db}}'
            )
        )
