import batou
import batou.component
import batou.utils
import os


class PostgresServer(batou.component.Component):

    listen_port = '5432'

    def configure(self):
        self.address = batou.utils.Address(self.host.fqdn, self.listen_port)
        self.provide('postgres', self)


class PostgresData(batou.component.Component):

    command_prefix = 'sudo -u postgres'

    def configure(self):
        self.require('postgres')
        for component in self.require(
                PostgresDataComponent.key, strict=False, reverse=True):
            self += component


class PostgresDataComponent(batou.component.HookComponent):

    key = 'postgres:config'

    def pgcmd(self, cmd, *args, **kw):
        return self.cmd('{} {}'.format(
            self.parent.command_prefix, cmd), *args, **kw)


class DB(PostgresDataComponent):

    namevar = 'db'

    def verify(self):
        try:
            self.pgcmd(
                self.expand('psql -c "SELECT true;" -d {{component.db}}'),
                silent=True)
        except Exception:
            raise batou.UpdateNeeded()

    def update(self):
        self.pgcmd(self.expand(
            'createdb -E UTF8 -O {{component.owner}} {{component.db}}'))


class User(PostgresDataComponent):

    namevar = 'user'

    def configure(self):
        assert self.password is not None, "Password for %s is None" % self.user

    def verify(self):
        os.environ['PGPASSWORD'] = self.password
        try:
            self.cmd(self.expand(
                'psql -d postgres -c "SELECT true;" -U {{component.user}} '
                '-w -h localhost postgres'),
                silent=True)
        except Exception:
            raise batou.UpdateNeeded()

    def update(self):
        command = self.expand(
            'sh -c "echo \\\"CREATE USER {{component.user}} '
            'PASSWORD \'{{component.password}}\' NOCREATEDB '
            'NOCREATEROLE NOSUPERUSER\\\" | psql -d postgres"'
        )
        self.pgcmd(command)
