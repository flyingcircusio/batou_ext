import batou
import batou.component
import batou.lib.cron
import batou.lib.file
import batou.lib.logrotate
import batou.lib.nagios
import batou.lib.service
import json
import os
import os.path
import pkg_resources


class Package(batou.component.Component):
    """Install Nix package for user.

    Usage:

        self += batou_ext.nix.Package('pbzip2-1.1.12')

    """

    namevar = 'package'
    attribute = None
    file = None

    def configure(self):
        if self.file:
            if not os.path.isabs(self.file):
                self.file = os.path.join(self.defdir, self.file)

    def verify(self):
        stdout, stderr = self.cmd('nix-env --query')
        if self.package not in stdout.splitlines():
            raise batou.UpdateNeeded()

    def update(self):
        if self.attribute:
            self.cmd('nix-env -iA {}'.format(self.attribute))
        elif self.file:
            self.cmd('nix-env -if {}'.format(self.file))
        else:
            self.cmd('nix-env -i {}'.format(self.package))


class Rebuild(batou.component.Component):
    """Trigger rebuild on FC platform.

    Usage::

        # Tirgger rebuild if self or subcomponent changed
        self += batou_ext.nix.Rebuild()

        # Trigger rebuild if specific components changed:
        self += batou_ext.nix.Rebuild(dependencies=(self, foo, bar))

    """

    dependencies = None

    def verify(self):
        if self.dependencies:
            for dependency in self.dependencies:
                dependency.assert_no_changes()
        else:
            self.parent.assert_no_subcomponent_changes()

    def update(self):
        self.cmd('sudo systemctl start fc-manage')


@batou.component.platform('nixos', batou.lib.service.Service)
class UserInit(batou.component.Component):
    """Start services on fc platform.

    Usage:

    * Import this module at least once in your deployment.
    * Set platform in environment to `nixos`.
    """

    def configure(self):
        self.env = os.environ
        self.executable = self.parent.executable
        self.name = os.path.basename(self.executable)
        self += batou.lib.file.File(
            '/etc/local/systemd/supervisor.service',
            content=pkg_resources.resource_string(
                'batou_ext', 'resources/supervisor.service'))
        self += Rebuild()


@batou.component.platform('nixos', batou.lib.cron.CronTab)
class InstallCrontab(batou.lib.cron.InstallCrontab):
    """Install crontab with crontab command."""

    def update(self):
        self.cmd(self.expand('cat {{component.crontab.path}} | crontab -'))


class SensuChecks(batou.component.Component):

    default_interval = 60

    def configure(self):
        self.services = self.require(batou.lib.nagios.Service.key,
                                     host=self.host)
        checks = {}
        for service in self.services:
            assert getattr(service, 'name', None)
            checks[service.name] = dict(
                interval=getattr(service, 'interval', self.default_interval),
                standalone=True,
                command=service.expand(
                    '{{component.command}} {{component.args}}'))

        sensu = dict(checks=checks)
        self += batou.lib.file.File(
            '/etc/local/sensu-client/batou.json',
            content=json.dumps(sensu, sort_keys=True, indent=4))


@batou.component.platform('nixos', batou.lib.logrotate.Logrotate)
class LogrotateIntegration(batou.component.Component):

    def configure(self):
        user = self.environment.service_user
        user_logrotate_conf = os.path.join(
            '/etc/local/logrotate', user, 'batou.conf')
        self += batou.lib.file.File(
            user_logrotate_conf,
            ensure='symlink',
            link_to=self.parent.logrotate_conf.path)
