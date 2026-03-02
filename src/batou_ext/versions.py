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


def find_versions_ini(environment: batou.environment.Environment):
    if "versions_ini" in environment.overrides["settings"]:
        return environment.overrides["settings"]["versions_ini"]
    elif os.path.exists("versions.ini"):
        return "versions.ini"
    else:
        raise ValueError(
            "No versions.ini specified in the environment file (via `settings.versions_ini`) and the file `versions.ini` does not exist in the git root, cannot proceed"
        )


def select_versions_interactive(basedir: str) -> dict:
    envs = os.listdir(os.path.join(basedir, "environments"))
    envs.sort()
    environment_name = inquirer.select(
        message="Select environment to update",
        choices=envs,
    ).execute()

    environment = batou.environment.Environment(environment_name)
    environment.load()

    versions = configparser.ConfigParser()
    versions_ini = find_versions_ini(environment)
    versions.read(os.path.join(basedir, versions_ini))

    components = versions.sections()
    selected_components = inquirer.select(
        message="Select components to update (Space to select, Ctrl-A for all):",
        choices=components,
        multiselect=True,
    ).execute()

    interative_versions = {}
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

        interative_versions[c] = new_version

    set_versions(versions_ini, interative_versions)
    return interative_versions


def get_current_versions(
    basedir: str, environment: batou.environment.Environment
):
    versions = configparser.ConfigParser()
    versions_ini = find_versions_ini(environment)
    versions.read(os.path.join(basedir, versions_ini))

    target_versions = {}
    for section in versions.sections():
        try:
            target_versions[section] = versions.get(section, "default")
        except configparser.NoOptionError:
            pass
    return target_versions


def update_from_branch(basedir: str, branch: str):
    branch_is_used = False
    envs = sorted(os.listdir(os.path.join(basedir, "environments")))

    for env_name in envs:
        environment = batou.environment.Environment(env_name)
        environment.load()

        if environment.branch != branch:
            continue

        branch_is_used = True

        print(f"Updating environment: {env_name}")
        current_versions = get_current_versions(basedir, environment)
        versions_ini = find_versions_ini(environment)
        set_versions(versions_ini, current_versions)

    if not branch_is_used:
        raise ValueError(
            f"Branch {branch} is not used in any environment, cannot auto-upate."
        )


def update_single(basedir: str, environment_name: str):
    environment = batou.environment.Environment(environment_name)
    environment.load()
    versions_ini = find_versions_ini(environment)
    current_versions = get_current_versions(basedir, environment)
    set_versions(versions_ini, current_versions)


def set_versions(versions_ini: str, target_versions: dict):
    updater = VersionsUpdater(versions_ini, json.dumps(target_versions))
    updater()
    subprocess.run(["git", "-P", "diff", versions_ini])


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

    if args.environment:
        update_single(basedir, args.environment)
    elif args.branch:
        update_from_branch(basedir, args.branch)
    else:
        select_versions_interactive(basedir)


if __name__ == "__main__":
    main()
