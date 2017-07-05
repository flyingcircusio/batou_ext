from batou import UpdateNeeded
from batou.component import Component, Attribute
from batou.lib.file import Directory, File, Purge
import os
import os.path


class SSHKeyPair(Component):

    """Install SSH user and host keys.

    User keys are read from the secrets file and written to
    ~/.ssh/id_rsa{,.pub} and/or ~/.ssh/id_ed25519{,.pub}."""

    # RSA-keys
    id_rsa = None
    id_rsa_pub = None

    # ed25510-keys
    id_ed25519 = None
    id_ed25519_pub = None

    scan_hosts = Attribute(list, '')
    provide_itself = Attribute('literal', True)
    purge_unmanaged_keys = Attribute('literal', False)

    def configure(self):
        if self.provide_itself:
            self.provide('sshkeypair', self)

        self += Directory('~/.ssh', mode=0o700)

        # RSA
        if self.id_rsa:
            self += File('~/.ssh/id_rsa',
                         content=self.id_rsa,
                         mode=0o600)
        elif self.purge_unmanaged_keys:
            self += Purge('~/.ssh/id_rsa')

        if self.id_rsa_pub:
            self += File('~/.ssh/id_rsa.pub',
                         content=self.id_rsa_pub)

        # ED25519
        if self.id_ed25519:
            self += File('~/.ssh/id_ed25519',
                         content='{}\n'.format(self.id_ed25519),
                         mode=0o600)

        elif self.purge_unmanaged_keys:
            self += Purge('~/.ssh/id_ed25519')

        if self.id_ed25519_pub:
            self += File('~/.ssh/id_ed25519.pub',
                         content=self.id_ed25519_pub)

        # ScanHost
        for host in self.scan_hosts:
            self += ScanHost(host)


class ScanHost(Component):

    """This component adds the host key of a provided host to the service
       user's known host file."""

    namevar = 'hostname'
    known_hosts = '~/.ssh/known_hosts'
    port = Attribute(int, 22)

    def configure(self):
        self.known_hosts = self.map(self.known_hosts)
        self += File(
            os.path.dirname(self.known_hosts),
            ensure='directory',
            mode=0o700,
            leading=True)

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
        self.cmd('ssh-keyscan -p {} "{}" >> "{}"'.format(
                 self.port, self.hostname, self.known_hosts))
