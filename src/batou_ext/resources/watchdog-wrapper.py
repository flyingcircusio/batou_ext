#!/usr/bin/env python

import logging
from argparse import ArgumentParser
from dataclasses import dataclass
from logging import info, warning
from math import ceil
from os import environ, execvp, fork
from subprocess import check_call
from time import sleep

import requests


@dataclass
class HealthCheckResult:
    success: bool
    summary: Exception | None = None

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        assert self.summary is not None
        return str(self.summary)


# Sentinel value for a successful healthcheck. Doesn't
# really make sense to instantiate a new HealthCheckResult whenever
# a healthcheck passes.
HEALTHCHECK_SUCCESS = HealthCheckResult(True)


class ExponentialBackoff:
    def __init__(self, static_check_interval: int):
        self.static_check_interval = static_check_interval
        self.last_healthcheck = HEALTHCHECK_SUCCESS
        self.__reset()

    def failure(self, last_failure_reason: HealthCheckResult):
        self.n_failures += 1
        self.last_healthcheck = last_failure_reason

    def sleep(self, timeout: int):
        seconds_to_sleep = self.static_check_interval + (2**self.n_failures)
        if self.last_healthcheck:
            self.__reset()
        else:
            self.__report_failing_healthcheck(
                seconds_to_sleep,
                self.__will_sleep_exceed_watchdog(timeout, seconds_to_sleep),
            )
            self.last_healthcheck = HEALTHCHECK_SUCCESS

        sleep(seconds_to_sleep)

    def __report_failing_healthcheck(
        self, sleep_seconds: int, will_time_out: bool
    ):
        log_message = f"Healthcheck failure (Reason: {self.last_healthcheck}), sleeping {sleep_seconds}."
        if will_time_out:
            warning(f"{log_message} Watchdog will likely kill process")
        else:
            info(log_message)

    def __will_sleep_exceed_watchdog(
        self, watchdog_timeout: int, seconds_to_sleep: int
    ) -> bool:
        # Seconds that were slept so far + seconds that will be slept.
        # This doesn't take the time spent with the healthcheck into account,
        # but that's only an approximation for logging.
        total_sleep = (
            # Seconds to be slept on the next sleep
            seconds_to_sleep
            # 2^n seconds of sleep for each 0 < n < self.n_failures
            + (2**self.n_failures - 2)
            # on each sleep it was additionally slept check_interval seconds
            + (self.n_failures - 1) * self.static_check_interval
        )

        return total_sleep >= watchdog_timeout

    def __reset(self):
        self.n_failures = 0


def is_service_available(url: str, timeout: int) -> HealthCheckResult:
    try:
        requests.get(url, timeout=timeout).raise_for_status()
        return HEALTHCHECK_SUCCESS
    except Exception as ex:
        return HealthCheckResult(False, ex)


def await_service(
    url: str, healthcheck_timeout: int, startup_loop_interval: int
):
    # No need to handle timeouts here: due to `Type=notify`,
    # this unit won't be up until this loop has terminated.
    # The timeout for that can be controlled in the unit directly
    # via TimeoutStartSec from `systemd.service(5)`.
    while not is_service_available(url, healthcheck_timeout):
        info(f"Service isn't up yet, sleeping {startup_loop_interval}s")
        sleep(startup_loop_interval)

    # Tell the service-manager that we're ready.
    # Because of this, the unit's state transitions from 'activating' to 'active'.
    check_call(["systemd-notify", "--ready"])
    info("Service ready, now monitoring.")


def monitor_service(
    url: str,
    watchdog_timeout: int,
    healthcheck_timeout: int,
    min_check_interval: int,
):
    # For WatchdogSec=32 with a sleep of 1s between all attempts there are three attempts
    # to recover.
    # I.e. 2^n seconds of sleep + 1s of sleep interval.
    # For each of the three attempts so far this is
    #   2^1 + 1 + 2^2 + 1 * 2^3 + 1 = 17s
    # because this is the fourth failure, a sleep of 2^4 + 1 seconds (=17s) will
    # be started . Since 17+17 > 32, the watchdog will kill the process before another
    # attempt can be made.
    #
    # The extra 1s (=min_check_interval) is added to provide a configurable grace period
    # between healthchecks. In some cases it may not be desirable to issue a healthcheck every second.
    exp_backoff = ExponentialBackoff(min_check_interval)

    while True:
        if result := is_service_available(url, healthcheck_timeout):
            check_call(["systemd-notify", "WATCHDOG=1"])
        else:
            exp_backoff.failure(result)

        exp_backoff.sleep(watchdog_timeout)


if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument(
        "--healthcheck-url",
        help="URL to issue a request against to check the service's health",
    )
    argparser.add_argument(
        "--healthcheck-timeout",
        default=2,
        type=int,
        help="How many seconds until the healthcheck request times out",
    )
    argparser.add_argument(
        "--watcher-loglevel",
        default="warning",
        help="Loglevel of the watchdog script, doen't influence the main process",
    )
    argparser.add_argument(
        "--startup-check-interval",
        default=4,
        type=int,
        help="Seconds to wait between healthchecks when the service is starting up",
    )
    argparser.add_argument(
        "--check-interval",
        default=2,
        type=int,
        help="Seconds to wait between healtchecks when the service is running",
    )
    argparser.add_argument(
        "command",
        nargs="+",
        help="Service process that will be watched by this script",
    )
    args = argparser.parse_args()

    # After how much time (in microseconds) the watchdog must be pet.
    # Set by systemd directly.
    assert (
        "WATCHDOG_USEC" in environ
    ), "WATCHDOG_USEC not in environment, please configure WatchdogSec in the systemd service!"
    watchdog_timeout = int(environ["WATCHDOG_USEC"]) // 1_000_000

    pid = fork()
    if pid > 0:
        # By making the service the main process, it will be restarted immediately when
        # the service crashes rather than waiting for the exponential backoff to fail.
        pass_args = args.command
        execvp(pass_args[0], pass_args)
    else:
        logging.basicConfig(level=args.watcher_loglevel.upper())
        info("Starting watcher for application as child process")

        await_service(
            args.healthcheck_url,
            args.healthcheck_timeout,
            args.startup_check_interval,
        )
        monitor_service(
            args.healthcheck_url,
            watchdog_timeout,
            args.healthcheck_timeout,
            args.check_interval,
        )
