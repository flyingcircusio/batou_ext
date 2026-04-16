# coding: utf8

import argparse
import socket
import sys
import time
import xmlrpc.client
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, Optional, Set, Tuple, Union

import batou
import batou.component
import batou.environment
import batou.lib.file
import batou.template
import configupdater


class DNSAliases(batou.component.Component):
    """Set up DNS aliases under the .fcio.net domain.

    NOTE: Requires batou >= 1.5

    Environment configuration example::

        [host:your-host]
        data-alias-srv =
            your-alias
            your-other-alias
        data-alias-fe =
            portal

        # The DNSAliases component is needed only *once* per environmnent.
        components =
            dnsaliases

        [component:dnsaliases]
        # Optional postfix
        postfix = .foo

        # Project (or as it used to be called: resource group)
        project = demo

        # api key should go into secrets!
        api_key = your-api-key

    The aliases will be: `<alias-from-host><postfix><project>.fcio.net`. The
    example produces:

    * your-alias.foo.demo.fcio.net -- pointing to SRV
    * your-other-alias.foo.demo.fico.net -- pointing to SRV
    * portal.foo.demo.fcio.net -- pointing to FE

    The aliases will point to the SRV addresses.

    """

    _required_params_ = {"project": "demo"}
    postfix = ""
    project = None
    api_key = None

    # How long to wait for aliases (seconds). 0: do not wait
    wait_for_aliases = batou.component.Attribute(int, default=0)

    # class variable:
    calls = []

    def configure(self):
        if self.calls:
            return
        self._compute_calls()
        self._call()
        self._wait_for_aliases()

    def _compute_calls(self):
        assert self.project
        self.aliases = []
        for host in list(self.environment.hosts.values()):
            self._add_calls(host.name, "srv", host.data.get("alias-srv"))
            self._add_calls(host.name, "fe", host.data.get("alias-fe"))
        self.calls.sort(key=lambda c: c["name"])

    def _call(self):
        api = xmlrpc.client.ServerProxy(
            "https://{s.project}:{s.api_key}@api.flyingcircus.io/v1".format(
                s=self
            )
        )
        api.apply(self.calls)

    def _add_calls(self, hostname, interface, aliases_str):
        if not aliases_str:
            return
        aliases = aliases_str.split()
        aliases.sort()
        self.calls.append(
            {
                "__type__": "virtualmachine",
                "name": hostname + self.postfix,
                "aliases_" + interface: aliases,
            }
        )
        self.aliases.extend(aliases)

    def _wait_for_aliases(self):
        if not self.wait_for_aliases:
            return
        batou.output.line(
            "Waiting up to %s seconds for aliases." % self.wait_for_aliases
        )
        started = time.time()
        error = True
        while started + self.wait_for_aliases > time.time():
            error, results = self._check_aliases()
            for result in results:
                batou.output.line(result)
            if not error:
                break
            time.sleep(10)
        if error:
            raise RuntimeError("Aliases did not resolve in time.")

    def _check_aliases(self):
        error = False
        results = []
        for alias in self.aliases:
            fqdn = "{}{}.{}.fcio.net".format(alias, self.postfix, self.project)
            try:
                addrs = socket.getaddrinfo(fqdn, None, 0, 0, socket.IPPROTO_TCP)
            except socket.gaierror as e:
                result = str(e)
                error = True
            else:
                result = ", ".join(
                    sockaddr[0]
                    for (family, type, proto, canonname, sockaddr) in addrs
                )
            results.append("{}: {}".format(fqdn, result))
        return error, results


API_URL = "https://{project}:{api_key}@api.flyingcircus.io/v1"


def create_xmlrpc_client(environment: batou.environment.Environment):
    try:
        rg_name = environment.overrides["provision"]["project"]
        api_key = environment.overrides["provision"]["api_key"]
    except KeyError:
        batou.output.error(
            "Expected section '[provision]' with keys 'project' and 'api_key' in the environment settings!"
        )
        raise
    api_url = environment.overrides["provision"].get("api_url", API_URL)
    api = xmlrpc.client.ServerProxy(
        api_url.format(project=rg_name, api_key=api_key)
    )
    return api


def convert_api_value(api_key: str, api_value: Any) -> Any:
    if api_key == "memory":
        if api_value is None:
            return None
        return str(int(api_value) // 1024)
    elif api_key == "classes":
        if isinstance(api_value, list):
            roles = [role.replace("role::", "") for role in api_value]
            roles = [r for r in roles if r and r != "generic"]
            roles.sort()
            return roles
        return api_value
    elif api_key in ["aliases_srv", "aliases_fe"]:
        if isinstance(api_value, list) and api_value:
            return sorted(api_value)
        return None
    elif api_key in ["cores", "disk", "rbd_pool", "service_description"]:
        return str(api_value) if api_value is not None else None
    else:
        return api_value


def format_cfg_value(value: Any) -> str:
    if value is None:
        return ""
    elif isinstance(value, list):
        return "\n    ".join(str(v) for v in value)
    else:
        return str(value)


def parse_cfg_value(item: Union[configupdater.Option, None]) -> Any:
    if item is None:
        return None

    value_str = item.value
    if value_str is None:
        return None

    value_str = value_str.strip()
    if not value_str:
        return None

    if "\n" in value_str:
        items = [item.strip() for item in value_str.split("\n") if item.strip()]
        return items if items else None

    try:
        result = eval(value_str)
        return result
    except:
        return value_str


def values_equal(val1: Any, val2: Any) -> bool:
    if val1 is None and val2 is None:
        return True
    if val1 is None or val2 is None:
        return False

    def normalize(v):
        if isinstance(v, str):
            if "\n" in v:
                items = [item.strip() for item in v.split("\n") if item.strip()]
                return sorted(items)
            else:
                return [v.strip()]
        elif isinstance(v, list):
            return sorted([str(item).strip() for item in v])
        else:
            return [str(v).strip()]

    return normalize(val1) == normalize(val2)


def get_config_vm_data(config: configupdater.ConfigUpdater) -> Dict[str, Dict]:
    vm_data = {}

    for section_name in config:
        if section_name.startswith("host:"):
            hostname = section_name[5:]
            vm_data[hostname] = {
                key: parse_cfg_value(item)
                for key, item in config[section_name].items()
            }

    return vm_data


def compare_vm_data(
    live_vm: Dict, config_vm: Dict, mode: str = "diff"
) -> Dict[str, Tuple]:
    updates = {}

    for api_key, cfg_key in [
        ("cores", "cores"),
        ("disk", "disk"),
        ("memory", "ram"),
        ("classes", "roles"),
        ("rbd_pool", "rbdpool"),
        ("service_description", "description"),
        ("aliases_srv", "alias-srv"),
        ("aliases_fe", "alias-fe"),
    ]:
        cfg_key_full = f"data-{cfg_key}"

        live_value = live_vm.get(api_key)
        config_value = config_vm.get(cfg_key_full)

        converted_live = convert_api_value(api_key, live_value)

        if converted_live is None or converted_live == "":
            continue

        if api_key == "service_description" and not converted_live:
            continue

        if mode == "all":
            updates[cfg_key_full] = (config_value, converted_live)
        elif mode == "diff":
            if not values_equal(converted_live, config_value):
                updates[cfg_key_full] = (config_value, converted_live)

    return updates


class Provision(batou.component.Component):
    """FCIO provisioning component.

    During a `batou deploy` run, this component does not do anything. It's
    there to hold the configuration.

    """

    project = None
    api_key = None
    location = "rzob"
    vm_environment_class = "NixOS"
    vm_environment = None

    # Passed by the CLI runner, not meant to be set via environment:
    env_name: str = None
    diff: dict = None
    dry_run: bool = None

    def load_env(self):
        environment = batou.environment.Environment(self.env_name)
        environment.load()
        environment.load_secrets()
        if environment.exceptions:
            # Yeah, this is awkward.
            batou.output = batou._output.Output(batou._output.TerminalBackend())
            for exc in environment.exceptions:
                exc.report()
            sys.exit(1)
        return environment

    def get_api(self):
        return create_xmlrpc_client(self.environment_)

    def get_currently_provisioned_vms(self):
        return self.api.query("virtualmachine")

    def apply(self):
        self.environment_ = self.load_env()
        self.api = self.get_api()

        def config(name):
            value = self.environment_.overrides["provision"].get(name)
            if not value:
                value = getattr(self, name)
            return value

        rg_name = config("project")

        vms = []
        for name, host in sorted(self.environment_.hosts.items()):
            d = host.data
            roles = d.get("roles", "").splitlines()
            classes = ["role::" + r for r in roles if r]

            if d.get("environment", config("vm_environment")) is None:
                raise ValueError(
                    "'environment' for {} must be set.".format(name)
                )

            call = dict(
                __type__="virtualmachine",
                cores=int(d["cores"]),
                disk=max(int(d["disk"]), 30),
                memory=int(d["ram"]) * 1024,
                online=True,
                name=host.name,
                classes=classes,
                resource_group=rg_name,
                environment_class=d.get(
                    "environment_class", config("vm_environment_class")
                ),
                environment=d.get("environment", config("vm_environment")),
                location=config("location"),
                rbd_pool=d.get("rbdpool", "rbd.hdd"),
                frontend_ips_v4=int(d.get("frontend-ipv4", 0)),
                frontend_ips_v6=int(d.get("frontend-ipv6", 0)),
                service_description=d.get("description", ""),
            )

            def alias(interface):
                aliases = d.get("alias-" + interface)
                if aliases:
                    aliases = aliases.split()
                    aliases.sort()
                    call["aliases_" + interface] = aliases

            alias("srv")
            alias("fe")

            vms.append(call)

        if self.diff:
            diff = self.get_diff(self.get_currently_provisioned_vms(), vms)
            print(
                "Applying the configuration to {env} would yield the following"
                " changes:\n".format(env=self.env_name)
            )

            for vm, changes in sorted(diff.items()):
                if changes:
                    print(vm)
                    for key, (old, new) in sorted(changes.items()):
                        if old or new:
                            print(
                                "    {key:20}: {old} → {new}".format(**locals())
                            )
                        else:
                            print("    {key}".format(**locals()))
                else:
                    print("{vm}: <no changes>".format(vm=vm))
        else:
            serviceuser = dict(
                __type__="serviceuser",
                uid=self.environment_.service_user,
                resource_group=rg_name,
                description="Deployment service user",
            )
            calls = [serviceuser] + vms
            if self.dry_run:
                pprint(calls)
            else:
                pprint(self.api.apply(calls))

    def get_diff(self, old, new):
        result = {}

        old = {vm["name"]: vm for vm in old}
        new = {vm["name"]: vm for vm in new}

        for vm_name, old_vm in list(old.items()):
            result[vm_name] = changes = {}
            new_vm = new.get(vm_name)
            if not new_vm:
                changes["VM exists and is unknown to deployment"] = (None, None)
                continue
            # starting with new because that only includes the data we
            # can set. We ignore all the other keys.
            for key, new_value in list(new_vm.items()):
                old_value = old_vm.get(key)
                if key == "classes":
                    # Roles need special treatment, generic is always included
                    try:
                        old_value.remove("role::generic")
                    except ValueError:
                        pass
                if old_value != new_value:
                    changes[key] = (old_value, new_value)
        for vm_name, new_vm in list(new.items()):
            if vm_name in result:
                continue
            result[vm_name] = {"CREATE VM": (None, None)}
            result[vm_name].update(
                {key: (None, value) for key, value in list(new_vm.items())}
            )
        return result

    def update_from_live(
        self,
        mode: str = "diff",
        verbose: bool = False,
        env_path: Optional[Path] = None,
    ):
        """Update environment.cfg from live FCIO API data."""
        self.environment_ = self.load_env()
        self.api = self.get_api()

        print(f"Loading environment: {self.env_name}")

        print("Connecting to FCIO API...")
        try:
            live_vms = {
                vm["name"]: vm for vm in self.api.query("virtualmachine")
            }
            print(f"Found {len(live_vms)} VMs in live data")
        except Exception as e:
            print(f"Error querying FCIO API: {e}", file=sys.stderr)
            sys.exit(1)

        if env_path is None:
            env_dir = Path("environments") / self.env_name
        else:
            env_dir = env_path
        cfg_path = env_dir / "environment.cfg"

        if not cfg_path.exists():
            print(f"Error: Config file not found: {cfg_path}", file=sys.stderr)
            sys.exit(1)

        config = configupdater.ConfigUpdater()
        config.read(cfg_path)

        config_vms = get_config_vm_data(config)
        print(f"Found {len(config_vms)} hosts in environment.cfg")

        live_only = set(live_vms.keys()) - set(config_vms.keys())
        config_only = set(config_vms.keys()) - set(live_vms.keys())

        if live_only:
            print(
                f"\nWarning: VMs in live data but not in config: {', '.join(sorted(live_only))}",
                file=sys.stderr,
            )
        if config_only:
            print(
                f"Warning: Hosts in config but not in live data: {', '.join(sorted(config_only))}",
                file=sys.stderr,
            )

        if live_only or config_only:
            print("(These will be ignored)", file=sys.stderr)

        print(f"\nComparing configurations (mode: {mode})...")

        updated_hosts = 0
        updated_fields = 0
        environment_values = set()

        common_vms = set(live_vms.keys()) & set(config_vms.keys())

        for hostname in sorted(common_vms):
            live_vm = live_vms[hostname]
            config_vm = config_vms[hostname]

            if "environment" in live_vm:
                environment_values.add(live_vm["environment"])

            updates = compare_vm_data(live_vm, config_vm, mode)

            if updates:
                section_name = f"host:{hostname}"
                if verbose:
                    print(f"\nUpdating [{section_name}]:")

                for cfg_key, (old_value, new_value) in sorted(updates.items()):
                    if cfg_key in config[section_name]:
                        if isinstance(new_value, list):
                            config[section_name][cfg_key].set_values(new_value)
                        else:
                            config[section_name][
                                cfg_key
                            ].value = format_cfg_value(new_value)
                    else:
                        if isinstance(new_value, list):
                            config[section_name][cfg_key] = configupdater.Block(
                                space_after=1
                            )
                            config[section_name][cfg_key].add_before(
                                format_cfg_value(new_value)
                            )
                        else:
                            config[section_name][cfg_key] = format_cfg_value(
                                new_value
                            )

                    if verbose:
                        old_str = (
                            str(old_value)
                            if old_value is not None
                            else "(not set)"
                        )
                        print(
                            f"  {cfg_key}: {old_str} → {format_cfg_value(new_value)}"
                        )

                    updated_fields += 1

                updated_hosts += 1

        if environment_values and len(environment_values) == 1:
            env_value = environment_values.pop()

            current_env = None
            if "component:provision" in config:
                if "vm_environment" in config["component:provision"]:
                    current_env = parse_cfg_value(
                        config["component:provision"]["vm_environment"]
                    )

            if mode == "all" or not values_equal(env_value, current_env):
                if "component:provision" not in config:
                    print(
                        "Warning: [component:provision] section not found",
                        file=sys.stderr,
                    )
                else:
                    config["component:provision"]["vm_environment"] = env_value
                    if verbose:
                        current_str = (
                            str(current_env)
                            if current_env is not None
                            else "(not set)"
                        )
                        print(f"\nUpdating [component:provision]:")
                        print(f"  vm_environment: {current_str} → {env_value}")
                    updated_fields += 1
        elif environment_values and len(environment_values) > 1:
            print(
                f"Warning: Conflicting environment values: {environment_values}",
                file=sys.stderr,
            )

        if updated_fields == 0:
            print("No updates needed")
            return

        print(
            f"\nUpdated {updated_fields} fields in {updated_hosts} host section(s)"
        )

        if self.dry_run:
            print("\nDry run mode - no changes will be made")
            if verbose:
                print("\nWould write:")
                print(str(config))
            return

        config.update_file()
        print(f"Updated {cfg_path}")


class DirectoryXMLRPC(batou.component.Component):
    rg_name = batou.component.Attribute(str, default=None)

    def configure(self):
        if not self.rg_name:
            self.rg_name = self.host.name[:-2]
        self.xmlrpc = create_xmlrpc_client(self.environment)
        self.provide("directory-xmlrpc", self)


class MaintenanceStart(batou.component.Component):
    """
    This component can be used to turn a resource group into maintenance.

    It consists of this component and ``MaintenanceEnd``. All components with

        self.provide("needs-maintenance")

    are scheduled in between.

    Please note that this causes an RG to be set into maintenance on each deploy
    (a follow-up with a suggestion is linked in FC-43347).

    The change is performed using the XML-RPC API of the directory. It is configured
    the same way as provisioning:

        [provision]
        project = abc
        api_key = aligator3

    The necessary components can be included like this:

        from batou_ext.fcio import MaintenanceStart, MaintenanceEnd, DirectoryXMLRPC

    and in the environment.cfg

        [host:test42]
        components =
          directoryxmlrpc
          maintenancestart
          maintenanceend

    By default, the resource group is derived by removing the last two letters
    from the host name. It's possible to set another resource group into maintenance
    with

        [component:directoryxmlrpc]
        rg_name = othertest
    """

    def configure(self):
        self.require("needs-maintenance", strict=False, reverse=True)
        self.xmlrpc = self.require_one("directory-xmlrpc")

    def verify(self):
        raise batou.UpdateNeeded()

    def update(self):
        change_maintenance_state(
            self.xmlrpc.xmlrpc, self.xmlrpc.rg_name, desired_state=True
        )


class MaintenanceEnd(batou.component.Component):
    def configure(self):
        self.require("needs-maintenance", strict=False)
        self.xmlrpc = self.require_one("directory-xmlrpc")

    def verify(self):
        raise batou.UpdateNeeded()

    def update(self):
        change_maintenance_state(
            self.xmlrpc.xmlrpc, self.xmlrpc.rg_name, desired_state=False
        )


def change_maintenance_state(
    xmlrpc, rg_name, desired_state, predict_only=False
):
    rg = next(
        (rg for rg in xmlrpc.query("resourcegroup") if rg["name"] == rg_name),
        None,
    )
    if rg is None:
        raise ValueError(
            f"Cannot change maintenance state of RG '{rg_name}', not in list of RGs modifyable with the xmlrpc API token."
        )

    if desired_state == rg["in_maintenance"]:
        batou.output.warn(
            f"Maintenance state of RG '{rg_name}' is already '{desired_state}'."
        )

    xmlrpc.apply(
        [
            {
                "__type__": "resourcegroup",
                "in_maintenance": desired_state,
                "name": rg_name,
            }
        ]
    )


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    p = subparsers.add_parser("provision", help="Apply resource settings")
    p.add_argument("env_name", help="Environment")
    p.add_argument("-n", "--dry-run", help="Dry run", action="store_true")
    p.add_argument(
        "-d", "--diff", help="Show changes in resources", action="store_true"
    )

    p.set_defaults(func=lambda **kw: Provision(**kw).apply())

    p = subparsers.add_parser(
        "update-env",
        help="Update environment.cfg from live FCIO API data",
    )
    p.add_argument("env_name", help="Environment")
    p.add_argument("-n", "--dry-run", help="Dry run", action="store_true")
    p.add_argument(
        "--all",
        help="Update ALL provisioned fields when using --update",
        action="store_true",
    )
    p.add_argument(
        "-v", "--verbose", help="Show detailed output", action="store_true"
    )

    def update_handler(*, env_name, **kw):
        provision = Provision(env_name=env_name, dry_run=kw.get("dry_run"))
        mode = "all" if kw.get("all") else "diff"
        provision.update_from_live(mode=mode, verbose=kw.get("verbose", False))

    p.set_defaults(func=update_handler)

    args = parser.parse_args()

    func_args = dict(args._get_kwargs())
    del func_args["func"]
    return args.func(**func_args)


if __name__ == "__main__":
    main()
