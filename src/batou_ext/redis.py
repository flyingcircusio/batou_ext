import batou.component
import batou.lib.file
import batou.utils
import batou_ext.nix


@batou_ext.nix.rebuild
class Redis(batou.component.Component):
    """Component to define Redis password and address
    """

    password = None

    password_file = "/etc/local/redis/password"
    port = 6379

    def configure(self):
        assert self.password
        self.provide("redis", self)

        self.address = batou.utils.Address(self.host.fqdn, self.port)
        self += batou.lib.file.File(self.password_file,
                                    content=self.password,
                                    sensitive_data=True)
