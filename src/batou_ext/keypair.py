from batou.component import Component
from batou.lib.file import File


class KeyPair(Component):

    namevar = 'name'

    crt = None
    key = None

    def configure(self):
        self.crt_file = File('{}.crt'.format(self.name), content=self.crt)
        self += self.crt_file
        self.key_file = File('{}.key'.format(self.name),
                             content=self.key,
                             mode=0o600)
        self += self.key_file

        self.provide('keypair::{}'.format(self.name), self)
