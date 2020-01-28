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
    """

    log_file = None
    lock_file = None
    stamp_file = None
    timeout = "1h"
    namevar = "tag"
    checkWarning = None  # minutes
    checkCritical = None  # minutes

    args = ""  # to satisfy sorting

    def format(self):
        return self.expand(
            """
{{component.timing}} \
 timeout {{component.timeout}} \
 {{component.wrapped_command}} \
 >> {{component.log_file}} 2>&1"""
        )

    def configure(self):
        self.provide(batou.lib.cron.CronJob.key, self)

        if self.timing is None:
            raise ValueError(
                "Required timing value missing from cron job %r."
                % self.command
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
