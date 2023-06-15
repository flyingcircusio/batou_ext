import os

import batou.component
import batou.lib.file
import batou.utils

import batou_ext.nix


@batou_ext.nix.rebuild
class Redis(batou.component.Component):
    """Component to define Redis password and address"""

    _required_params_ = {
        "password": "tiger",
    }
    password = None

    password_file = "/etc/local/redis/password"
    port = 6379

    # Number of database you are connecting
    db = batou.component.Attribute(int, default=0)

    cleanup = batou.component.Attribute("literal", default=False)
    cleanup_command = batou.component.Attribute(str, default="FLUSHDB")

    def configure(self):
        assert self.password
        self.provide("redis", self)

        self.address = batou.utils.Address(self.host.fqdn, self.port)
        self += batou.lib.file.File(
            self.password_file, content=self.password, sensitive_data=True
        )
        if self.cleanup:
            self += batou.lib.file.File(
                "rediscleanup.sh",
                source=self.resource("rediscleanup.sh"),
                mode=0o755,
            )
            self += batou_ext.run.Run("rediscleanup.sh", file=self._)

    def resource(self, filename):
        return os.path.join(os.path.dirname(__file__), "resources", filename)
