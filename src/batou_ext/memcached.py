import json

import batou.component
import batou.lib.file
import batou.utils

import batou_ext.config
import batou_ext.nix


@batou_ext.nix.rebuild
class Memcached(batou.component.Component):
    """
    Helps to configure memcached

    Usage:
    self += batou_ext.memached.Memcached(
        port=11211,
        custom_config=dict(foo='baa', zzz=11))
    """

    port = batou.component.Attribute(int, 11211)

    # A additional dict
    custom_config = {}

    def configure(self):
        self.provide("memcached", self)
        self.address = batou.utils.Address(self.host.fqdn, self.port)

        # Trying to set some sane defaults
        base_config = dict(
            maxMemory=1024,
            port=self.port,
            maxConnections=1024,
        )

        config = batou_ext.config.dict_merge(base_config, self.custom_config)

        self += batou.lib.file.File(
            "/etc/local/memcached/memcached.json", content=json.dumps(config)
        )
