import collections
import hashlib
import inspect
import json
import os
import os.path
import shlex
import subprocess
import time
from pathlib import Path

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
from batou import (
    IPAddressConfigurationError,
    ReportingException,
    UpdateNeeded,
    output,
)
from batou.component import Component, RootComponent
from batou.environment import Environment
from batou.host import Host
from batou.lib.file import (
    File,
    Group,
    ManagedContentBase,
    Mode,
    Owner,
    Presence,
)
from batou.utils import Address, NetLoc


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
            self.cmd(f"nix-env --query {self.package}")
            raise batou.UpdateNeeded()
        except batou.utils.CmdExecutionError as e:
            if e.stderr.strip().endswith("matches no derivations"):
                batou.output.annotate(
                    f"Could not find package to purge: {self.package}",
                    yellow=True,
                )
            else:
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


def nix_dict_to_nix(dct):
    """Converts a dict with values that are already nixified to Nix code."""
    content = " ".join(f"{n} = {v};" for n, v in dct.items())
    return "{ " + content + " }"


def seq_to_nix(seq):
    content = " ".join(value_to_nix(v) for v in seq)
    return "[ " + content + " ]"


def mapping_to_nix(obj):
    # XXX: only str keys for now

    converted = {}
    for k, v in obj.items():
        conv = value_to_nix(v)
        if conv is not None:
            converted[k] = conv
    return nix_dict_to_nix(converted)


def str_to_nix(value):
    # https://nixos.org/manual/nix/stable/language/values.html#type-string
    value = (
        value.replace("\\", "\\\\").replace("${", "\\${").replace('"', '\\"')
    )
    return f'"{value}"'


def environment_to_nix_dict(env: Environment):
    dct = {
        "base_dir": str_to_nix(env.base_dir),
        "connect_method": str_to_nix(env.connect_method),
        "deployment_base": str_to_nix(env.deployment_base),
        "name": str_to_nix(env.name),
        "target_directory": str_to_nix(env.target_directory),
        "workdir_base": str_to_nix(env.workdir_base),
    }

    if env.host_domain is not None:
        dct["host_domain"] = str_to_nix(env.host_domain)
    if env.platform is not None:
        dct["platform"] = str_to_nix(env.platform)
    if env.service_user is not None:
        dct["service_user"] = str_to_nix(env.service_user)

    return dct


def netloc_to_nix_dict(netloc: NetLoc):
    return {
        "__toString": f'_: "{netloc}"',
        "host": str_to_nix(netloc.host),
        "port": str(netloc.port),
    }


def address_to_nix_dict(addr: Address):
    dct = {
        "__toString": f"_: {str_to_nix(str(addr))}",
        "connect": nix_dict_to_nix(netloc_to_nix_dict(addr.connect)),
    }
    try:
        dct["listen"] = nix_dict_to_nix(netloc_to_nix_dict(addr.listen))
    except IPAddressConfigurationError:
        pass
    try:
        dct["listen_v6"] = nix_dict_to_nix(netloc_to_nix_dict(addr.listen_v6))
    except IPAddressConfigurationError:
        pass

    return dct


def host_to_nix_dict(host: Host):
    return {"fqdn": str_to_nix(host.fqdn), "name": str_to_nix(host.name)}


def value_to_nix(value):
    if isinstance(value, str):
        return str_to_nix(value)
    elif isinstance(value, bool):
        return str(value).lower()
    elif value is None:
        return None
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, Path):
        return str(value)
    elif isinstance(value, dict):
        return mapping_to_nix(value)
    elif isinstance(value, list):
        return seq_to_nix(value)
    elif isinstance(value, tuple):
        return seq_to_nix(value)
    elif isinstance(value, Component):
        return component_to_nix(value)
    elif isinstance(value, Address):
        return nix_dict_to_nix(address_to_nix_dict(value))
    elif isinstance(value, Host):
        return nix_dict_to_nix(host_to_nix_dict(value))
    elif isinstance(value, Environment):
        return nix_dict_to_nix(environment_to_nix_dict(value))
    elif isinstance(value, batou.utils.Timer):
        return None  # ignore
    else:
        raise TypeError(f"unsupported type '{type(value)}'")


def component_to_nix(component: Component):
    from batou_ext.nixos import NixOSModuleContext

    attrs = {}

    for name, value in inspect.getmembers(component):
        if name.startswith("_"):
            pass
        elif value is component:
            pass
        elif inspect.ismethod(value) or inspect.isgenerator(value):
            pass
        elif name in ("sub_components", "changed"):
            pass
        elif isinstance(value, NixOSModuleContext):
            pass
        elif isinstance(value, RootComponent):
            if (
                value.component is not component
                and component.parent is not value.component
            ):
                attrs[name] = component_to_nix(value.component)
        elif isinstance(value, Component):
            if value is not component.parent:
                attrs[name] = component_to_nix(value)
        elif isinstance(value, NixOSModuleContext):
            pass
        else:
            try:
                converted_value = value_to_nix(value)
                if converted_value is not None:
                    attrs[name] = converted_value
            except TypeError as e:
                component.log(f"Cannot convert {name}: {e.args[0]}")

    return nix_dict_to_nix(attrs)


class NixSyntaxCheckFailed(ReportingException):
    def __init__(self, error_msg, path=None):
        self.error_msg = error_msg.strip().removeprefix("error: ")
        self.path = path

    def __str__(self):
        return f"Nix syntax check failed: {self.error_msg} in {self.path}"

    def report(self):
        output.error(f"Nix check {self.error_msg}")


class NixContent(ManagedContentBase):
    format_nix_code = False
    check_nix_syntax = True

    def render(self):
        pass

    def verify(self, predicting=False):
        update_needed = False

        if self.format_nix_code:
            try:
                proc = subprocess.run(
                    ["nixfmt"],
                    input=self.content,
                    check=True,
                    capture_output=True,
                )
                self.content = proc.stdout
            except FileNotFoundError:
                self.log("Cannot format Nix file, nixfmt not found.")
            except subprocess.CalledProcessError as e:
                self.log(f"nixfmt failed: {e.stderr}")

        try:
            super().verify(predicting)
        except UpdateNeeded:
            update_needed = True

        if self.check_nix_syntax:
            try:
                subprocess.run(
                    ["nix-instantiate", "--parse", "-"],
                    input=self.content,
                    check=True,
                    capture_output=True,
                )
            except FileNotFoundError:
                self.log(
                    "Cannot syntax-check Nix file, nix-instantiate not found."
                )
            except subprocess.CalledProcessError as e:
                raise NixSyntaxCheckFailed(
                    e.stderr.decode("utf8"), path=self.path
                )

        if update_needed:
            raise UpdateNeeded()


class NixFile(File):
    format_nix_code = False

    def configure(self):
        self._unmapped_path = self.path
        self.path = self.map(self.path)
        self += Presence(self.path, leading=self.leading)

        # variation: content or source explicitly given

        # The mode needs to be set early to allow batou to get out of
        # accidental "permission denied" situations.
        if self.mode:
            self += Mode(self.path, mode=self.mode)

        # no content or source given but file with same name
        # exists
        if self.content is None and not self.source:
            guess_source = self.root.defdir + "/" + os.path.basename(self.path)
            if os.path.isfile(guess_source):
                self.source = guess_source
            else:
                # Avoid the edge case where we want to support a very simple
                # case: specify File('asdf') and have an identical named file
                # in the component definition directory that will be templated
                # to the work directory.
                #
                # However, if you mis-spell the file, then you might
                # accidentally end up with an empty file in the work directory.
                # If you really want an empty File then you can either use
                # Presence(), or (recommended) use File('asdf', content='') to
                # make this explicit. We don't want to accidentally confuse the
                # convenience case (template a simple file) and an edge case
                # (have an empty file)
                raise ValueError(
                    "Missing implicit template file {}. Or did you want "
                    "to create an empty file? Then use File('{}', content='').".format(
                        guess_source, self._unmapped_path
                    )
                )
        if self.content or self.source:
            content = NixContent(
                self.path,
                source=self.source,
                encoding=self.encoding,
                content=self.content,
                sensitive_data=self.sensitive_data,
                format_nix_code=self.format_nix_code,
            )
            self += content
            self.content = content.content

        if self.owner:
            self += Owner(self.path, owner=self.owner)

        if self.group:
            self += Group(self.path, group=self.group)
