"""Helper for Jenkins pipeline deployments."""

import argparse
import configparser
import json
import subprocess
import sys


def git_resolve(url, version):
    if len(version) == 40:
        # revision.
        try:
            int(version, 16)
        except ValueError:
            pass
        else:
            return version
    # Symbolic name?
    cmd = subprocess.Popen(
        ["git", "ls-remote", url, version + "^{}"], stdout=subprocess.PIPE
    )
    stdout, stderr = cmd.communicate()
    # if its not a tag, start another more generic attempt
    if not stdout:
        cmd = subprocess.Popen(
            ["git", "ls-remote", url, version], stdout=subprocess.PIPE
        )
        stdout, stderr = cmd.communicate()
    stdout = stdout.decode("ascii")
    return stdout.split("\t", 1)[0]


class VersionsUpdater:
    UPDATERS = {
        "git-resolve": "update_git",
        "pass": "update_pass_value",
    }

    def __init__(self, versions_file, version_mapping_json):
        self.version_mapping = json.loads(version_mapping_json)
        self.versions_file = versions_file
        self.config = configparser.ConfigParser()
        self.config.read(self.versions_file)

    def __call__(self):
        for service, version in sorted(self.version_mapping.items()):
            if not version:
                # leave empty to keep current version
                continue
            self.update(service, version)

        with open(self.versions_file, "w") as f:
            self.config.write(f)
            # Remove the trailing newline, which pre-commit doesn't like:
            f.truncate(f.tell() - 1)

    def update(self, service, version):
        update_mode = self.config[service].get("update", "git-resolve")
        update_mode = update_mode.split(":", 1)
        mode = update_mode[0]
        args = "".join(update_mode[1:])

        func = getattr(self, self.UPDATERS[mode])
        func(service, version, args)

    def update_git(self, service, version, extra_args):
        resolved = git_resolve(self.config.get(service, "url"), version)
        if not resolved:
            raise ValueError(
                "%s: Could not resolve version %s." % (service, version)
            )
        log("%s: resolved version %s to: %s", service, version, resolved)
        self.config.set(service, "revision", resolved)
        self.config.set(service, "version", version)

    def update_pass_value(self, service, version, extra_args):
        self.config[service][extra_args] = version


def log(msg, *args):
    print(msg % args)
    sys.stdout.flush()


def list_components(versions_file, verbose=False):
    config = configparser.SafeConfigParser()
    config.read(versions_file)
    components = sorted(config.sections())
    if verbose:
        result = []
        for component in components:
            c = dict(config.items(component))
            c["name"] = component
            result.append(c)
    else:
        result = components

    print(json.dumps(result, sort_keys=True))


def set_versions(versions_file, version_mapping_json):
    vu = VersionsUpdater(versions_file, version_mapping_json)
    vu()


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    p = subparsers.add_parser(
        "list-components",
        help="List available components where versions can be set",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Return all options from versions.ini, not only component names",
    )
    p.add_argument("versions_file", help='Name of "versions.ini"')
    p.set_defaults(func=list_components)

    p = subparsers.add_parser("set-versions", help="Update versions")
    p.add_argument(
        "versions_file",
        help="Name of versions.ini. If exists it will be overwritten.",
    )
    p.add_argument(
        "version_mapping_json", help="JSON: mapping of service: version"
    )
    p.set_defaults(func=set_versions)

    args = parser.parse_args()
    func_args = dict(args._get_kwargs())
    del func_args["func"]
    return args.func(**func_args)


if __name__ == "__main__":
    main()
