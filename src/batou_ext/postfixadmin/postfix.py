import os
import socket

from batou.component import Attribute, Component, ConfigString
from batou.lib.file import File
from batou.utils import Address


def resolve_v6(address):
    return socket.getaddrinfo(
        address.connect.host, address.connect.port, socket.AF_INET6
    )[0][4][0]


class PFAPostfix(Component):

    address = Attribute(Address, ConfigString("localhost:25"))

    def configure(self):
        self.address.listen.host_v6 = resolve_v6(self.address)

        self.db = self.require_one("pfa::database")
        self.keypair = self.require_one("keypair::mail")

        self.provide("postfix", self.address)

        self += File(
            "/etc/postfix/myhostname", content=self.address.connect.host
        )
        self += File(
            "/etc/postfix/main.d/40_local.cf", source=self.resource("local.cf")
        )
        self += File(
            "postfixadmin_virtual_alias",
            source=self.resource("postfixadmin_virtual_alias"),
        )
        self += File(
            "postfixadmin_virtual_domains",
            source=self.resource("postfixadmin_virtual_domains"),
        )
        self += File(
            "postfixadmin_virtual_sender_login",
            source=self.resource("postfixadmin_virtual_sender_login"),
        )
        self += File(
            "postfixadmin_virtual_mailboxes",
            source=self.resource("postfixadmin_virtual_mailboxes"),
        )

    def resource(self, filename):
        return os.path.join(os.path.dirname(__file__), "postfix", filename)
