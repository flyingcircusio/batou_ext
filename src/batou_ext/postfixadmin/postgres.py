from batou.component import Component
from batou.utils import Address

class Postgres(Component):

    def configure(self):
        self.address = Address(self.host.fqdn, 5432)
        self.provide('pfa::database', self)
