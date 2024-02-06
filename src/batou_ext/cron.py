from textwrap import dedent

import batou.component
import batou.lib.nagios
import pkg_resources


class CronJob(batou.component.Component):
    """Improved cronjob with locking, timeout, logging, and monitoring

    See https://blog.flyingcircus.io/2015/04/16/improving-periodic-data-import-jobs-in-3-steps/
    for motivation etc.

    Usage::

        self += batou_ext.cron.CronJob(
            "cleanup",
            command="bin/cleanup some stuff",
            timing="*/4 * * * * ",
            timeout="3m",
            checkWarning=6,
            checkCritical=10)

    Where `tag` is an identifier from which is derived: script name,
    lock file, log file, stamp file.

    `checkWarning` and `checkCritical` should be given in minutes since
    last update of the stamp-file (=last successfully run of cronJob)
    and will turn the service check into warning or critical state after
    these times were exceeded.
    Ensure this values are fitting the settings done within `timing`.

    Please note, that this component requires you to import the
    `Logrotate` component (`from batou.lib.logrotate import Logrotate`)
    and add it to the components list of the host on which you want to
    deploy the cronjob.

    e.g.

            [host:yourhost]
                components =
                    ...
                    logrotate
    """  # noqa: E501 line too long

    _required_params_ = {"timing": "*/4 * * * * "}
    namevar = "tag"

    command = None
    timing = None
    log_file = None
    lock_file = None
    stamp_file = None
    timeout = "1h"
    checkWarning = None  # minutes
    checkCritical = None  # minutes

    args = ""  # to satisfy sorting

    def format(self):
        return self.expand(
            """\
{{component.timing}} \
 timeout {{component.timeout}} \
 {{component.wrapped_command}} \
 >> {{component.log_file}} 2>&1"""
        )

    def configure(self):
        self.provide(batou.lib.cron.CronJob.key, self)

        if self.timing is None:
            raise ValueError(
                "Required timing value missing from cron job %r." % self.command
            )

        self += batou.lib.file.File("logs", ensure="directory")
        self.log_file = self.map(self.expand("logs/{{component.tag}}.log"))
        self += batou.lib.logrotate.RotatedLogfile(self.log_file)

        self.lock_file = self.map(self.expand(".{{component.tag}}.lock"))
        self.stamp_file = self.map(self.expand(".{{component.tag}}.stamp"))

        # Ensure, we do have the stamp file there so the sensu-check is
        # getting red if next runs are not successful
        self += batou.lib.file.File(self.stamp_file, content="")

        self += batou.lib.file.File(
            self.expand("{{component.tag}}.sh"),
            content=pkg_resources.resource_string(
                __name__, "resources/cron-wrapper.sh"
            ),
            mode=0o755,
        )
        self.wrapped_command = self._.path

        if self.checkWarning or self.checkCritical:
            cmd = ["-f", self.stamp_file]
            if self.checkWarning:
                cmd.append("-w")
                cmd.append(str(int(self.checkWarning) * 60))
            if self.checkCritical:
                cmd.append("-c")
                cmd.append(str(int(self.checkCritical) * 60))

            self += batou.lib.nagios.Service(
                self.expand("Cronjob {{component.tag}} finished?"),
                command="check_file_age",
                args=" ".join(cmd),
                name=self.expand("cronjob_{{component.tag}}"),
            )


class SystemdTimer(batou.component.Component):
    """Integration for systemd timers with *FC nixos*.


    Usage::

        self += batou_ext.cron.SystemdTimer(
            "cleanup",
            command="bin/cleanup some stuff",
            onCalendar="*:0/5",
            timeout="3m")

    See https://www.freedesktop.org/software/systemd/man/systemd.time.html
    for details about the `onCalendar` timer settings.

    If `persistent` is set to True, the time when the service unit was last
    triggered is stored on disk.
    When the timer is activated, the service unit is triggered immediately
    if it would have been triggered at least once during the time when
    the timer was inactive.

    For deployments, this usually means that the unit is started immediately
    after, without waiting for the next scheduled activation.
    """

    _required_params_ = {"command": "/bin/true", "onCalendar": "02:00:00"}

    namevar = "tag"
    command = batou.component.Attribute(str)
    onCalendar = batou.component.Attribute(str)
    persistent = batou.component.Attribute("literal", False)
    timeout = "1h"
    description = None
    additional_service_config = None
    run_as = batou.component.Attribute(
        str,
        default=batou.component.ConfigString(
            "{{component.environment.service_user}}"
        ),
    )

    def configure(self):
        if self.description is None:
            self.description = f"Batou generated unit for {self.tag}"

        self += batou.lib.file.File(
            self.expand("{{component.tag}}.sh"),
            mode=0o755,
            content=dedent(
                f"""\
                #!/bin/sh

                # This file is generated by batou and run by systemd
                # via `{self.tag}.timer` and `{self.tag}.service`.

                source /etc/profile
                set -exo pipefail

            """
            )
            + self.command,
        )
        self.wrapped_command = self._.path

        if isinstance(self.persistent, bool) and self.persistent:
            self.persistent_timer_config = "true"
        else:
            self.persistent_timer_config = "false"

        self += batou.lib.file.File(
            f"/etc/local/nixos/timer-{self.tag}.nix",
            content=dedent(
                """\
              { ... }:
              {
                systemd.timers."{{component.tag}}" = {
                  wantedBy = [ "timers.target" ];
                  timerConfig = {
                    OnCalendar = "{{component.onCalendar}}";
                    Persistent = {{component.persistent_timer_config}};
                  };
                };

                systemd.services."{{component.tag}}" = {
                  description = "{{component.description}}";
                  serviceConfig = {
                    Type = "oneshot";
                    User = "{{component.run_as}}";
                    ExecStart = "{{component.wrapped_command}}";
                    TimeoutStartSec = "{{component.timeout}}";
                    {%- if component.additional_service_config is not none %}
                    {%- for setting, value in component.additional_service_config.items() %}
                    {{ setting }} = {{ value }};
                    {%- endfor %}
                    {%- endif %}
                  };
                };
              }
        """
            ),
        )

        self += batou.lib.file.File(
            self.expand("check_systemd_unit.py"),
            content=pkg_resources.resource_string(
                __name__, "resources/check_systemd_unit.py"
            ),
            mode=0o755,
        )
        self.check_command = self._.path
        self += batou.lib.nagios.Service(
            f"Timer/Unit {self.tag} ok?",
            command=self.check_command,
            args=self.tag,
            name=f"timer_{self.tag}",
        )
