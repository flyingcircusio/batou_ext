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
            'PASSWORD \'{{component.password}}\' NOCREATEDB '
            'NOCREATEROLE NOSUPERUSER\\\" | psql -d postgres"'
        )
        self.pgcmd(command)
