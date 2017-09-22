import batou
import batou.component
import batou.lib.cron
import batou.lib.file
import batou.lib.logrotate
import batou.lib.nagios
import batou.utils
import batou.lib.service
import batou.lib.supervisor
import collections
import json
import os
import os.path
import pkg_resources
import time


class Package(batou.component.Component):
    """Install Nix package for user.

    Usage:

        self += batou_ext.nix.Package(attribute='nixos.yarn')
        self += batou_ext.nix.Package('pbzip2-1.1.12')

    """

    package = None
    attribute = None
    file = None

    def __init__(self, namevar=None, **kw):
        # Make 'namevar' optional
        kw['package'] = namevar
        super(Package, self).__init__(**kw)

    def configure(self):
        if self.file:
            assert self.package
            if not os.path.isabs(self.file):
                self.file = os.path.join(self.defdir, self.file)

    def verify(self):
        if self.attribute:
            stdout, stderr = self.cmd('nix-env -qaA {{component.attribute}}')
            would_install = stdout.strip()
        else:
            would_install = self.package
        stdout, stderr = self.cmd('nix-env --query')
        if would_install not in stdout.splitlines():
            raise batou.UpdateNeeded()

    def update(self):
        if self.attribute:
            self.cmd('nix-env -iA {}'.format(self.attribute))
        elif self.file:
            self.cmd('nix-env -if {}'.format(self.file))
        else:
            self.cmd('nix-env -i {}'.format(self.package))

    @property
    def namevar_for_breadcrumb(self):
        return self.attribute if self.attribute else self.package


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
        self.cmd('sudo fc-manage --build')


def rebuild(cls):
    """Class decctorator easily allow rebuild in multi platform environments.

    This is possible and useful because restarting or reconfiguring services
    on NixOS always is *just* a rebuild.

    Usage::

        @batou_ext.nix.rebuild
        class Foo(batou.component.Component):
            ...

    """
    cls._add_platform('nixos', Rebuild)
    return cls


@batou.component.platform('nixos', batou.lib.service.Service)
class UserInit(batou.component.Component):
    """Start services on fc platform.

    Usage:

    * Import this module at least once in your deployment.
    * Set platform in environment to `nixos`.
    """

    def configure(self):
        self.executable = self.parent.executable
        self.name = os.path.basename(self.executable)

        self.service = dict(
            Type='forking',
            LimitNOFILE='64000',
            LimitNPROC='64173',
            LimitSIGPENDING='64173',
            User=self.environment.service_user,
            Group='service',
            ExecStart=os.path.join(self.root.workdir, self.executable))

        self.service.update(getattr(self.parent, 'systemd', {}))
        self.checksum = getattr(self.parent, 'checksum', '')
        self += batou.lib.file.File(
            '/etc/local/systemd/{}.service'.format(self.name),
            content=pkg_resources.resource_string(
                'batou_ext', 'resources/systemd.service'))
        self += Rebuild()

    @property
    def env(self):
        env = collections.defaultdict(dict)
        env.update(os.environ)
        return env

    def start(self):
        self.cmd('sudo systemctl start {}'.format(self.name))


@batou.component.platform('nixos', batou.lib.supervisor.RunningSupervisor)
class FixSupervisorStartedBySystemd(batou.component.Component):
    """For some, yet unknown reason, supervisor is not started with systemd.

    To fix it, we need to restart supervisor.

    """

    def verify(self):
        if not self.parent.is_running():
            # Well, if it's not running, something is really hosed.
            return
        try:
            self.cmd('sudo systemctl status supervisord')
        except batou.utils.CmdExecutionError:
            # Aha. IT's running, but not by systemd!
            raise batou.UpdateNeeded

    def update(self):
        self.cmd('bin/supervisorctl shutdown')
        wait = 60
        while wait:
            out, err = '', ''
            out, err = self.cmd('bin/supervisorctl pid',
                                ignore_returncode=True)
            if 'no such file' in out:
                break
            time.sleep(1)
            wait -= 1

        self.cmd('sudo systemctl start supervisord')


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


class PythonWithNixPackages(batou.component.Component):
    """Provide a python interpreter which contains packages from nix.

    Usage:


    Provides "python3.5" pointing to the path of the executable.

    """

    python = None  # expython interpreter, "python3.5"
    nix_packages = ()  # sequence of nix package attributes

    def configure(self):
        self += batou.lib.file.File(
            '{}.nix'.format(self.python),
            content=pkg_resources.resource_string(
                'batou_ext', 'resources/python.nix'))
        self += batou.lib.file.File(
            '{}.c'.format(self.python),
            content=pkg_resources.resource_string(
                'batou_ext', 'resources/loader.c'))
        self += batou.lib.file.File(
            'setupEnv-{}'.format(self.python), mode=0o755,
            content=pkg_resources.resource_string(
                'batou_ext', 'resources/setupEnv.sh'))
        self.provide(self.python, os.path.join(self.workdir, self.python))

    def verify(self):
        self.assert_no_subcomponent_changes()

    def update(self):
        self.cmd('gcc {}.c -o {}'.format(self.python, self.python))
        # Start up once to load all dependencies here and not upon the first
        # use:
        self.cmd('./{} -c True'.format(self.python))
