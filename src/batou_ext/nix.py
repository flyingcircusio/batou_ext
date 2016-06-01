import batou
import batou.component
import batou.lib.cron
import batou.lib.service
import os
import pkg_resources


class Package(batou.component.Component):
    """Install Nix package for user.

    Usage:

        self += batou_ext.nix.Package('pbzip2-1.1.12')

    """

    namevar = 'package'

    def verify(self):
        stdout, stderr = self.cmd('nix-env --query')
        if self.package not in stdout.splitlines():
            raise batou.UpdateNeeded()

    def update(self):
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
