from batou import UpdateNeeded
from batou.component import Component, Attribute
from batou.lib.file import Directory, File
import batou.c
import os
import os.path


class SSHKeyPair(Component):

    """Install SSH user and host keys.

    User keys are read from the secrets file and written to
    ~/.ssh/id_rsa{,.pub}.  """

    id_rsa = None
    id_rsa_pub = None
    scan_hosts = Attribute(list, '')
    provide_itself = Attribute(bool, True)

    def configure(self):
        if self.provide_itself:
            self.provide('sshkeypair', self)

        self += Directory('~/.ssh', mode=0o711)

        if self.id_rsa:
            self += File('~/.ssh/id_rsa',
                         content=self.id_rsa,
                         mode=0o600)
        else:
            self += batou.c.common.AbsentFile('~/.ssh/id_rsa')

        if self.id_rsa_pub:
            self += File('~/.ssh/id_rsa.pub',
                         content=self.id_rsa_pub)

        for host in self.scan_hosts:
            self += ScanHost(host)


class ScanHost(Component):

    """This component adds the host key of a provided host to the service
       user's known host file."""

    namevar = 'hostname'
    known_hosts = '~/.ssh/known_hosts'

    def configure(self):
        self.known_hosts = self.map(self.known_hosts)

    def verify(self):
        if not os.path.exists(self.known_hosts):
            raise UpdateNeeded()
        with open(self.known_hosts, 'r') as f:
            content = f.read()
        if self.hostname not in content:
            raise UpdateNeeded()

    def update(self):
        try:
            del os.environ['SSH_AUTH_SOCK']
        except KeyError:
            pass
        self.cmd('ssh-keyscan "{}" >> "{}"'.format(
                 self.hostname, self.known_hosts))

