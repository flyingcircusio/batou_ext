import batou
import batou.component
import batou.lib.file
import json
import socket
import time
import xmlrpclib


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

    postfix = ''
    project = None
    api_key = None

    # How long to wait for aliases (seconds). 0: do not wait
    wait_for_aliases = batou.component.Attribute(int, 0)

    def configure(self):
        assert self.project
        self.calls = []
        self.aliases = []
        for host in self.environment.hosts.values():
            self._add_calls(
                host.name, 'srv', host.data.get('alias-srv'))
            self._add_calls(
                host.name, 'fe', host.data.get('alias-fe'))
        self.calls.sort(key=lambda c: c['name'])
        self += batou.lib.file.File(
            'state.json', content=json.dumps(self.calls))

    def verify(self):
        if self.api_key:
            self.assert_no_changes()
            if self.wait_for_aliases:
                error, results = self._check_aliases()
                if error:
                    raise batou.UpdateNeeded()

    def update(self):
        api = xmlrpclib.ServerProxy(
            'https://{s.project}:{s.api_key}@api.flyingcircus.io/v1'.format(
                s=self))
        api.apply(self.calls)
        self._wait_for_aliases()

    def _add_calls(self, hostname, interface, aliases_str):
        if not aliases_str:
            return
        aliases = aliases_str.split()
        aliases.sort()
        self.calls.append({
            '__type__': 'virtualmachine',
            'name': hostname + self.postfix,
            'aliases_' + interface: aliases})
        self.aliases.extend(aliases)

    def _wait_for_aliases(self):
        if not self.wait_for_aliases:
            return
        batou.output.line('Waiting up to %s seconds for aliases.'
                          % self.wait_for_aliases)
        started = time.time()
        while started + self.wait_for_aliases > time.time():
            error, results = self._check_aliases
            for result in results:
                output.line(result)
            if error:
                time.sleep(10)

    def _check_aliases(self):
        error = False
        for alias in self.aliases:
            fqdn = '{}.{}.{}.fcio.net'.format(
                alias, self.postfix, self.project)
            try:
                addrs = socket.getaddrinfo(
                    fqdn, None, 0, 0, socket.IPPROTO_TCP)
            except socket.gaierror, e:
                result = str(e)
                error = True
            else:
                result = ', '.join(
                    canonname
                    for (family, type, proto, canonname, sockaddr)
                    in result)
            results.append('{}: {}'.format(fqdn, result))
        return error, results
