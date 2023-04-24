# coding: utf8

import argparse
import socket
import sys
import time
import xmlrpc.client
from pprint import pprint

import batou
import batou.component
import batou.environment
import batou.lib.file
import batou.template


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
    api_url = "https://{project}:{api_key}@api.flyingcircus.io/v1"

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
        rg_name = self.environment_.overrides["provision"]["project"]
        api_key = self.environment_.overrides["provision"]["api_key"]
        api_url = self.environment_.overrides["provision"].get("api_url")
        if not api_url:
            api_url = self.api_url
        api = xmlrpc.client.ServerProxy(
            api_url.format(project=rg_name, api_key=api_key)
        )
        return api

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

    args = parser.parse_args()

    func_args = dict(args._get_kwargs())
    del func_args["func"]
    return args.func(**func_args)


if __name__ == "__main__":
    main()
