import batou
import batou.component
import batou.lib.file
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

    # class variable:
    calls = []

    def configure(self):
        # This is a bit pointless now...
        self.provide('dnsaliases', self)
        if self.calls:
            return
        self._compute_calls()
        self._call()
        self._wait_for_aliases()

    def _compute_calls(self):
        assert self.project
        self.aliases = []
        for host in self.environment.hosts.values():
            self._add_calls(
                host.name, 'srv', host.data.get('alias-srv'))
            self._add_calls(
                host.name, 'fe', host.data.get('alias-fe'))
        self.calls.sort(key=lambda c: c['name'])

    def _call(self):
        api = xmlrpclib.ServerProxy(
            'https://{s.project}:{s.api_key}@api.flyingcircus.io/v1'.format(
                s=self))
        api.apply(self.calls)

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
        error = True
        while started + self.wait_for_aliases > time.time():
            error, results = self._check_aliases()
            for result in results:
                batou.output.line(result)
            if not error:
                break
            time.sleep(10)
        if error:
            raise RuntimeError('Aliases did not resolve in time.')

    def _check_aliases(self):
        error = False
        results = []
        for alias in self.aliases:
            fqdn = '{}{}.{}.fcio.net'.format(
                alias, self.postfix, self.project)
            try:
                addrs = socket.getaddrinfo(
                    fqdn, None, 0, 0, socket.IPPROTO_TCP)
            except socket.gaierror as e:
                result = str(e)
                error = True
            else:
                result = ', '.join(
                    sockaddr[0]
                    for (family, type, proto, canonname, sockaddr) in addrs)
            results.append('{}: {}'.format(fqdn, result))
        return error, results
