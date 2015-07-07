from batou.component import Component
from batou.lib.file import File
from batou.utils import Address
import socket


def resolve_v6(address):
    return socket.getaddrinfo(
        address.connect.host,
        address.connect.port,
        socket.AF_INET6)[0][4][0]


class Postfix(Component):

    namevar = 'address'

    def configure(self):
        self.address = Address(self.address, 25)
        self.address.listen.host_v6 = resolve_v6(self.address)

        self.db = self.require_one('pfa::database')
#        self.db.database = self.db.databases[0]
#        self.shared = self.require_one('pfa_keypair')

#        self.provide('pfa_postfix', self.address)

#        self += File('/etc/postfix/myhostname',
#                     content=self.address.connect.host)
#        self += File('/etc/postfix/main.d/40_local.cf')
#        self += File('postfixadmin_virtual_alias')
#        self += File('postfixadmin_virtual_domains')
#        self += File('postfixadmin_virtual_sender_login')
#        self += File('postfixadmin_virtual_mailboxes')
