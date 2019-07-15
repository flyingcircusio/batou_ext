import batou
import batou.component
import batou.utils
import os


class PostgresServer(batou.component.Component):

    listen_port = '5432'

    def configure(self):
        self.address = batou.utils.Address(self.host.fqdn, self.listen_port)
        self.provide('postgres', self)


class PostgresDataComponent(batou.component.Component):

    def pgcmd(self, cmd, *args, **kw):
        return self.cmd('{} {}'.format(
            self.parent.command_prefix, cmd), *args, **kw)


class DB(PostgresDataComponent):

    namevar = 'db'
    locale = 'en_US.UTF-8'

    def verify(self):
        try:
            self.pgcmd(
                self.expand('psql -c "SELECT true;" -d {{component.db}}'),
                silent=True)
        except batou.utils.CmdExecutionError:
            raise batou.UpdateNeeded()

    def update(self):
        self.pgcmd(self.expand(
            'createdb -l {{component.locale}} -O {{component.owner}} '
            '{{component.db}}'))


class User(PostgresDataComponent):

    namevar = 'name'
    flags = 'NOCREATEDB NOCREATEROLE NOSUPERUSER'

    def configure(self):
        super(User, self).configure()
        assert self.password is not None, "Password for %s is None" % self.name

    def verify(self):
        os.environ['PGPASSWORD'] = self.password
        try:
            self.cmd(self.expand(
                'psql -d postgres -c "SELECT true;" -U {{component.name}} '
                '-w -h localhost'))
        except batou.utils.CmdExecutionError:
            raise batou.UpdateNeeded()
        finally:
            del os.environ['PGPASSWORD']

    def update(self):
        command = self.expand(
            'sh -c "echo \\\"CREATE USER {{component.name}} '
            'PASSWORD \'{{component.password}}\' '
            '{{component.flags}} \\\" | psql -d postgres"'
        )
        self.pgcmd(command)


class Extension(PostgresDataComponent):
    """
        Creats an extension to a given PostgreSQL-DB.

        Please note: The extensions needs to be already present in context
        of the database cluser.

        Usage:

        self += batou_ext.postgres.Extension(
            'uuid-ossp',
            db='my_database')

    """

    namevar = "extension_name"
    db = None

    def configure(self):
        if self.extension_name is None:
            raise ValueError("Need to set extension name")
        if self.db is None:
            raise ValueError(
                "Need to specify a database to "
                "create extension in")

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
