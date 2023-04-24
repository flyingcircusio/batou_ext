import os

from batou.component import Attribute, Component
from batou.lib.file import File


class KeyPair(Component):

    namevar = "name"
    _required_params_ = {
        "crt": "certificate",
        "key": "key",
    }

    crt = None
    key = None

    base_path = Attribute(str, "")
    provide_itself = Attribute(bool, default=True)

    def configure(self):
        self.crt_file = File(
            os.path.join(self.base_path, "{}.crt".format(self.name)),
            content=self.crt,
        )
        self += self.crt_file
        self.key_file = File(
            os.path.join(self.base_path, "{}.key".format(self.name)),
            content=self.key,
            mode=0o600,
        )
        self += self.key_file

        if self.provide_itself:
            self.provide("keypair::{}".format(self.name), self)
