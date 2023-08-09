import collections
import hashlib
import json
import os
import os.path
import shlex
import time

import batou
import batou.component
import batou.lib.cron
import batou.lib.file
import batou.lib.logrotate
import batou.lib.nagios
import batou.lib.service
import batou.lib.supervisor
import batou.utils
import pkg_resources


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
        kw["package"] = namevar
        super(Package, self).__init__(**kw)

    def configure(self):
        if self.file:
            assert self.package
            if not os.path.isabs(self.file):
                self.file = os.path.join(self.defdir, self.file)

    def verify(self):
        if self.attribute:
            stdout, stderr = self.cmd("nix-env -qaA {{component.attribute}}")
            self._installs_package = stdout.strip()
        else:
            self._installs_package = self.package
        stdout, stderr = self.cmd("nix-env --query")
        if self._installs_package not in stdout.splitlines():
            raise batou.UpdateNeeded()

    def update(self):
        if self.attribute:
            self.cmd("nix-env -iA {{component.attribute}}")
        elif self.file:
            self.cmd("nix-env -if {{component.file}}")
        else:
            self.cmd("nix-env -i {{component.package}}")

    @property
    def namevar_for_breadcrumb(self):
        return self.attribute if self.attribute else self.package


class PurgePackage(batou.component.Component):

    namevar = "package"

    def verify(self):
        try:
            self.cmd("nix-env --query {{component.package}}")
            raise batou.UpdateNeeded()
        except batou.utils.CmdExecutionError as e:
            e.report()

    def update(self):
        self.cmd("nix-env --uninstall {{component.package}}")


class UserEnv(batou.component.Component):
    """Provide a NixOS user environment.

    Usage::
        self += batou_ext.nix.UserEnv(
                "django",
                packages=[
                    "gcc",
                    "gettext",
                    "glibc",
                    "liberation_ttf",
                    "libffi",
                    "libxml2",
                    "libxslt",
                    "mysql55",
                    "nodejs-8_x",
                    "openssl",
                    "python27Full",
                    "yarn",
                    "zip",
                ],
                channel="<nixos-channel-base-url-to-be-put-in>/nixexprs.tar.xz"
                shellInit="# additional shell init")

    A list of available channels can be found at e.g.
    https://nixos.org/channels/
    """

    namevar = "profile_name"
    channel = batou.component.Attribute(str)
    shellInit = ""
    packages = ()
    let_extra = ""

    def configure(self):
        self.checksum = hashlib.sha256()
        template = pkg_resources.resource_string(
            __name__, "resources/userenv.nix"
        ).decode("UTF-8")
        self.profile = self.expand(template).encode("UTF-8")
        self.checksum.update(self.profile)
        self.nix_env_name = self.expand(
            "{{component.profile_name}}-1.{{component.checksum.hexdigest()}}"
        )
        self += batou.lib.file.File(
            self.profile_name + ".nix", content=self.profile
        )
        self += Package(self.nix_env_name, file=self._.path)
        self.user_profile_path = os.path.expanduser(
            "~/.nix-profile/etc/profile.d/{}.sh".format(self.profile_name)
        )
        self.user_bin_path = os.path.expanduser("~/.nix-profile/bin")


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
        self.cmd("sudo fc-manage --build")


def rebuild(cls):
    """Class decctorator easily allow rebuild in multi platform environments.

    This is possible and useful because restarting or reconfiguring services
    on NixOS always is *just* a rebuild.

    Usage::

        @batou_ext.nix.rebuild
        class Foo(batou.component.Component):
            ...

    """
    cls._add_platform("nixos", Rebuild)
    return cls


# Uhugh. Patch service so we can set checksum/systemd data which is being used
# by UserInit.
batou.lib.service.Service.checksum = ""
batou.lib.service.Service.systemd = None


@batou.component.platform("nixos", batou.lib.service.Service)
class UserInit(batou.component.Component):
    """Start services on fc platform.

    Usage:

    * Import this module at least once in your deployment.
    * Set platform in environment to `nixos`.
    """

    def configure(self):
        self.executable = self.parent.executable
        name = shlex.split(self.executable)[0]
        name = os.path.basename(name)
        self.name = os.path.splitext(name)[0]

        # Remove older versions that were created with
        # hard-to-read or broken service filenames to avoid accidental
        # duplicates.
        service_file = "/etc/local/systemd/{}.service".format(self.name)
        old_service_file = "/etc/local/systemd/{}.service".format(
            os.path.basename(self.executable)
        )
        if old_service_file != service_file:
            self += batou.lib.file.Purge(old_service_file)

        # The systemd config namespace of our expected systemd dictionary
        # is a little messed up.
        #
        # You can use
        # - bare config attribute names, those will end up in the [Service]
        #   section
        # - <Section>_<Attribute>, those will end up in the respective
        #   [<Section>] sections.
        #
        # E.g. systemd=dict(Unit_After='afdsfdasfsda', Service_Type='Simple',
        #                  User='nobody')
        config = {}
        config["Unit"] = {"X-Restart-Triggers": self.parent.checksum}
        config["Service"] = dict(
            Type="forking",
            LimitNOFILE="64000",
            LimitNPROC="64173",
            LimitSIGPENDING="64173",
            User=self.environment.service_user,
            Group="service",
            ExecStart=os.path.join(self.root.workdir, self.executable),
            Restart="always",
            Environment=[
                self.expand(
                    "LOCALE_ARCHIVE={{component.env['LOCALE_ARCHIVE']}}"
                ),
                self.expand("PATH={{component.env['PATH']}}"),
                self.expand("TZDIR={{component.env['TZDIR']}}"),
            ],
        )

        # Phase 1: allow overriding keys, do not append lists
        systemd = self.parent.systemd or {}
        for key, value in list(systemd.items()):
            if "_" in key:
                section, key = key.split("_", 1)
            else:
                section = "Service"
            config.setdefault(section, {})[key] = value

        # Phase 2: expand (trivial) iterables into multiple keys
        self.config = {}
        for section in config:
            self.config[section] = []
            for key, value in list(config[section].items()):
                if not isinstance(value, (list, tuple)):
                    value = [value]
                for v in value:
                    self.config[section].append((key, v))

        self.checksum = self.parent.checksum
        self += batou.lib.file.File(
            service_file,
            content=pkg_resources.resource_string(
                "batou_ext", "resources/systemd.service"
            ),
        )
        self += Rebuild()

    @property
    def env(self):
        env = collections.defaultdict(dict)
        env.update(os.environ)
        return env

    def start(self):
        self.cmd("sudo systemctl start {}".format(self.name))

    def verify(self):
        self.assert_cmd("sudo systemctl is-active {}".format(self.name))

    def update(self):
        self.start()


@batou.component.platform("nixos", batou.lib.supervisor.RunningSupervisor)
class FixSupervisorStartedBySystemd(batou.component.Component):
    """For some, yet unknown reason, supervisor is not started with systemd.

    To fix it, we need to restart supervisor.

    """

    def verify(self):
        if not self.parent.is_running():
            # Well, if it's not running, something is really hosed.
            return
        try:
            self.cmd("sudo systemctl status supervisord")
        except batou.utils.CmdExecutionError:
            # Aha. IT's running, but not by systemd!
            raise batou.UpdateNeeded

    def update(self):
        self.cmd("bin/supervisorctl shutdown")
        wait = 60
        while wait:
            out, err = "", ""
            out, err = self.cmd("bin/supervisorctl pid", ignore_returncode=True)
            if "no such file" in out:
                break
            time.sleep(1)
            wait -= 1

        self.cmd("sudo systemctl start supervisord")


@batou.component.platform("nixos", batou.lib.cron.CronTab)
class InstallCrontab(batou.lib.cron.InstallCrontab):
    """Install crontab with crontab command."""

    def update(self):
        self.cmd(self.expand("cat {{component.crontab.path}} | crontab -"))


# Patch Service so we can pass down the name to sensu
batou.lib.nagios.Service.name: str = None
batou.lib.nagios.Service.interval: int = 60
batou.lib.nagios.Service.cron: str = None


@rebuild
class SensuChecks(batou.component.Component):
    """SensuChecks gathers ServiceChecks and creates sensu checks accordingly.

    This is a substitute for batou.lib.nagios.NRPEHost.

    `ServiceCheck` instances require an additional attribute `name`, to
    identify the check::

        self += ServiceCheck(
            'Testname',
            name='accounting',
            ...)


    The default execution interval is 60 seconds, and can be changed by
    setting `interval` on the ServiceCheck instance, e.g.::

        self += ServiceCheck(
            'Testname',
            name='accounting',
            command='/path/to/checker',
            args="--my-check-args",
            interval=120)

    Sensu also supports a cron notation:

        self += ServiceCheck(
            'Testname',
            name='accounting',
            command='/path/to/checker',
            args="--my-check-args",
            interval=None,
            cron="*5/ 3-7 * * *")


    """

    purge_old_batou_json = batou.component.Attribute("literal", default=True)

    def configure(self):
        self.services = self.require(
            batou.lib.nagios.Service.key, host=self.host
        )
        checks = {}
        for service in self.services:
            assert getattr(service, "name", None)
            checks[service.name] = check = dict(
                standalone=True,
                command=service.expand(
                    "{{component.command}} {{component.args}}"
                ),
            )

            if service.interval:
                check["interval"] = service.interval
            elif service.cron:
                check["cron"] = service.cron
            else:
                raise ValueError("Need either `interval` or `cron` setting.")

        config_file_name = "/etc/local/sensu-client/{}-batou.json".format(
            self.environment.service_user
        )

        if checks:
            sensu = dict(checks=checks)

            self += batou.lib.file.File(
                config_file_name,
                content=json.dumps(sensu, sort_keys=True, indent=4),
            )
        else:
            self += batou.lib.file.Purge(config_file_name)

        if self.purge_old_batou_json:
            self += batou.lib.file.Purge("/etc/local/sensu-client/batou.json")


@batou.component.platform("nixos", batou.lib.logrotate.Logrotate)
class LogrotateIntegration(batou.component.Component):
    def configure(self):
        assert (
            self.environment.service_user
        ), "Need to set service_user inside environment file."
        user = self.environment.service_user
        user_logrotate_conf = os.path.join(
            "/etc/local/logrotate", user, "batou.conf"
        )
        self += batou.lib.file.File(
            user_logrotate_conf, content=self.parent.logrotate_conf.content
        )


class PythonWithNixPackages(batou.component.Component):
    """Provide a python interpreter which contains packages from nix.

    Usage:


    Provides "python3.5" pointing to the path of the executable.

    """

    _required_params_ = {"python": "python3.5"}
    # python interpreter, "python3.5"
    python = None

    # sequence of nix package attributes
    # this must include the actual python, .i.e.  pkgs.python34
    nix_packages = ()
    pythonPackages = None

    def configure(self):
        if not self.pythonPackages:
            self.pythonPackages = "pkgs.{}Packages".format(
                self.python.replace(".", "")
            )

        self += batou.lib.file.File(
            "{}.nix".format(self.python),
            content=pkg_resources.resource_string(
                "batou_ext", "resources/python.nix"
            ),
        )
        self += batou.lib.file.File(
            "setupEnv-{}".format(self.python),
            mode=0o755,
            content=pkg_resources.resource_string(
                "batou_ext", "resources/setupEnv.sh"
            ),
        )
        self.env_file = self._
        self += batou.lib.file.File(
            "{}.c".format(self.python),
            content=pkg_resources.resource_string(
                "batou_ext", "resources/loader.c"
            ),
        )
        self.provide(self.python, os.path.join(self.workdir, self.python))

    def verify(self):
        self.assert_no_subcomponent_changes()

    def update(self):
        self.cmd("gcc {}.c -o {}".format(self.python, self.python))
        # Start up once to load all dependencies here and not upon the first
        # use:
        self.cmd("./{} -c True".format(self.python))
