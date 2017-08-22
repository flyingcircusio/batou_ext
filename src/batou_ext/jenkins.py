"""Helper for Jenkins pipeline deployments."""

from __future__ import print_function
import ConfigParser
import argparse
import json
import subprocess
import sys


def log(msg, *args):
    print(msg % args)
    sys.stdout.flush()


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
    cmd = subprocess.Popen(['git', 'ls-remote', url, version],
                           stdout=subprocess.PIPE)
    stdout, stderr = cmd.communicate()
    return stdout.split('\t', 1)[0]


def set_versions(versions_file, version_mapping_json):
    version_mapping = json.loads(version_mapping_json)

    config = ConfigParser.SafeConfigParser()
    config.read(versions_file)

    for service, version in sorted(version_mapping.items()):
        if not version:
            # leave empty to keep current version
            continue
        resolved = git_resolve(config.get(service, 'url'), version)
        log('%s: resolved version %s to: %s', service, version, resolved)
        config.set(service, 'revision', resolved)
        config.set(service, 'version', version)

    with open(versions_file, 'w') as f:
        config.write(f)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    p = subparsers.add_parser(
        'set-versions',
        help='Update versions')
    p.add_argument(
        'versions_file',
        help='Name of versions.ini. If exists it will be overwritten.')
    p.add_argument(
        'version_mapping_json',
        help='JSON: mapping of service: version')
    p.set_defaults(func=set_versions)

    args = parser.parse_args()
    func_args = dict(args._get_kwargs())
    del func_args['func']
    return args.func(**func_args)


if __name__ == '__main__':
    main()
