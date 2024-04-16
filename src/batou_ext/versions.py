import argparse
import configparser
import json
import os
import os.path
import subprocess
import sys

import batou.environment
from InquirerPy import inquirer
from prompt_toolkit.completion import FuzzyWordCompleter, ThreadedCompleter

from batou_ext.jenkins import VersionsUpdater


def get_git_version_completer(url):
    def get_words():
        cmd = subprocess.Popen(
            ["git", "ls-remote", url], stdout=subprocess.PIPE, encoding="UTF-8"
        )
        stdout, stderr = cmd.communicate()
        words = []
        for line in stdout.splitlines():
            words.extend(line.split())
        return words

    return ThreadedCompleter(FuzzyWordCompleter(get_words))


class Updater:
    """Version update, interactive or automatic."""

    environment_name: str = None
    _environment = None
    _target_versions = None

    def __init__(self, basedir):
        self.basedir = basedir

    @property
    def environment(self):
        if self._environment is None:
            assert self.environment_name
            self._environment = batou.environment.Environment(
                self.environment_name
            )
            self._environment.load()
        return self._environment

    def update_from_branch(self, branch: str):
        envs = sorted(os.listdir(os.path.join(self.basedir, "environments")))
        for env_name in envs:
            env = batou.environment.Environment(env_name)
            env.load()
            if env.branch == branch:
                print(f"Updating environment: {env_name}")
                self.environment_name = env_name
                self.set_versions()

        if not self.environment_name:
            raise ValueError(
                f"Branch {branch} is not used in any environment, "
                "cannot auto-upate."
            )

    @property
    def versions_ini(self):
        if "versions_ini" in self.environment.overrides["settings"]:
            return self.environment.overrides["settings"]["versions_ini"]
        elif os.path.exists("versions.ini"):
            return "versions.ini"
        else:
            raise ValueError(
                "No versions.ini specified in the environment file (via `settings.versions_ini`) and the file `versions.ini` does not exist in the git root, cannot proceed"
            )

    def interactive(self):
        envs = os.listdir(os.path.join(self.basedir, "environments"))
        envs.sort()
        self.environment_name = inquirer.select(
            message="Select environment to update",
            choices=envs,
        ).execute()

        versions = configparser.ConfigParser()
        versions.read(os.path.join(self.basedir, self.versions_ini))
        components = versions.sections()
        selected_components = inquirer.select(
            message="Select components to update (Space to select, Ctrl-A for all):",
            choices=components,
            multiselect=True,
        ).execute()

        self._target_versions = {}
        for c in selected_components:
            try:
                default = versions.get(c, "default")
            except configparser.NoOptionError:
                default = ""

            git_url = versions[c].get("url")
            if git_url:
                git_completer = get_git_version_completer(git_url)
            else:
                git_completer = None
            new_version = inquirer.text(
                message=f"Update {c} to:",
                default=default,
                completer=git_completer,
            ).execute()

            self._target_versions[c] = new_version

    def set_versions(self):
        if self._target_versions is None:
            self._target_versions = {}
            versions = configparser.ConfigParser()
            versions.read(os.path.join(self.basedir, self.versions_ini))
            for section in versions.sections():
                try:
                    self._target_versions[section] = versions.get(
                        section, "default"
                    )
                except configparser.NoOptionError:
                    pass

        updater = VersionsUpdater(
            self.versions_ini, json.dumps(self._target_versions)
        )
        updater()
        subprocess.run(["git", "-P", "diff", self.versions_ini])


def main():
    basedir = os.environ.get("APPENV_BASEDIR", os.path.dirname(sys.argv[0]))

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--update-defaults",
        dest="environment",
        help="Auto-update all versions to their specified defaults.",
    )
    parser.add_argument(
        "-b",
        "--branch",
        dest="branch",
        help="Update environment matching the branch.",
    )

    parser.add_argument(
        "-d",
        "--base-dir",
        dest="basedir",
        help="Deployment base dir",
        default=basedir,
    )

    args = parser.parse_args()

    update = Updater(args.basedir)

    if args.environment:
        update.environment_name = args.environment
        update.set_versions()
    elif args.branch:
        update.update_from_branch(args.branch)
    else:
        update.interactive()
        update.set_versions()


if __name__ == "__main__":
    main()
