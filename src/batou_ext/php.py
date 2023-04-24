"""Components for managing PHP.

Example for NixOS::


    class PHPApp(batou.component.Component):

        def configure(self):
            self.settings = self.require_one("settings")

            self += batou_ext.nix.UserEnv(
                "portal",
                packages=["php71", "php71Packages.redis"],
            )

            self += batou_ext.php.Ini(settings="", extensions=["redis.so"])
            self += batou_ext.php.FPM(
                "portal", dependency_strings=(self._.php_ini.content,)
            )

"""

import hashlib
import os.path

import batou.component
import batou.lib.file
import pkg_resources


class Ini(batou.component.Component):
    """Manage php.ini."""

    extensions = ()
    settings = ""
    logs = None

    def configure(self):
        self._extensions_dir = os.path.expanduser(
            "~/.nix-profile/lib/php/extensions/"
        )

        if self.logs is None:
            self.logs = self.map("logs")
        self += batou.lib.file.File(self.logs, leading=True, ensure="directory")
        self.error_log = os.path.join(self.logs, "php-error.log")
        self += batou.lib.logrotate.RotatedLogfile(
            self.error_log,
            postrotate="kill -USR1 $(cat {}/php-fpm.pid)".format(self.workdir),
        )

        # Providing a php.ini
        self += batou.lib.file.File(
            "php.ini",
            content=pkg_resources.resource_string(
                __name__, "resources/php/php.ini"
            ),
        )
        self.php_ini = self._


class FPM(batou.component.Component):
    """Provde running FPM.

    Usage::

        self += batou_ext.php.FPM("myphpproject")

    """

    name = None
    namevar = "name"

    php_ini = None  # defaults to `php.ini` in workdir
    logs = None  # defaults to `logs` in workdir

    global_settings = ""
    pool_settings = ""

    port = 9001

    env = {}  # Additional environmental values for FPM
    keep_env = batou.component.Attribute("literal", default=False)

    dependency_strings = ()

    def configure(self):
        self._checksum = hashlib.new("sha256")
        for s in self.dependency_strings:
            if isinstance(s, str):
                self._checksum.update(s.encode("utf-8"))
            else:
                self._checksum.update(s)

        self.address = batou.utils.Address(self.host.fqdn, self.port)

        # Logging
        if self.logs is None:
            self.logs = self.map("logs")
        self += batou.lib.file.File(self.logs, leading=True, ensure="directory")
        self.slow_log = os.path.join(self.logs, "slow.log")
        self += batou.lib.logrotate.RotatedLogfile(
            self.slow_log,
            postrotate="kill -USR1 $(cat {}/php-fpm.pid)".format(self.workdir),
        )

        # fpm.ini

        # Ensure we don't clear up environment if there is an env
        if self.env:
            self.keep_env = True

        self += batou.lib.file.File(
            "php-fpm.conf",
            content=pkg_resources.resource_string(
                __name__, "resources/php/php-fpm.conf"
            ),
        )
        self._checksum.update(self._.content)
        self.php_fpm_ini = self._.path

        if self.php_ini is None:
            self.php_ini = self.map("php.ini")

        # Start script
        self.pid_file = self.map("php-fpm.pid")
        self += batou.lib.file.File(
            self.name,
            mode=0o755,
            content=pkg_resources.resource_string(
                __name__, "resources/php/php-fpm.sh"
            ),
        )
        self._checksum.update(self._.content)

        # Service startup. We expect the service to be monitored by a generic
        # systemd "all proceses are running" check.
        self += batou.lib.service.Service(
            self.name,
            checksum=self._checksum.hexdigest(),
            systemd=dict(PIDFile=self.pid_file, Restart="always"),
        )
