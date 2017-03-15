import batou.component
import batou.lib.file
import json
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

    def configure(self):
        assert self.project
        self.calls = []
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

    def update(self):
        api = xmlrpclib.ServerProxy(
            'https://{s.project}:{s.api_key}@api.flyingcircus.io/v1'.format(
                s=self))
        api.apply(self.calls)

    def _add_calls(self, hostname, interface, aliases_str):
        aliases = []
        if aliases_str:
            aliases.extend(aliases_str.split())
        aliases.sort()
        self.calls.append(dict(
            __type__='virtualmachine',
            name=hostname + self.postfix,
            aliases=aliases))
