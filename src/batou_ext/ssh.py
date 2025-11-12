import os
import os.path

import batou
import batou.utils
from batou.component import Attribute, Component
from batou.lib.file import File, Purge


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

    file_name = Attribute(str, default=None)

    scan_hosts = Attribute("list", default=[])
    provide_itself = Attribute("literal", default=True)
    purge_unmanaged_keys = Attribute("literal", default=False)
    provide_as = Attribute(str, default="sshkeypair")

    def configure(self):
        if self.provide_itself:
            self.provide(self.provide_as, self)

        self += File("~/.ssh", ensure="directory", mode=0o700)

        if self.file_name is not None:
            if self.id_rsa and self.id_ed25519:
                raise ValueError(
                    "When setting `file_name`, using both id_rsa and id_ed25519 is not supported!"
                )

            file_name_rsa = self.file_name
            file_name_ed25519 = self.file_name
        else:
            file_name_rsa = "id_rsa"
            file_name_ed25519 = "id_ed25519"

        # RSA
        if self.id_rsa:
            self += File(
                f"~/.ssh/{file_name_rsa}",
                content=(self.id_rsa + "\n"),
                mode=0o600,
                sensitive_data=True,
            )
        elif self.purge_unmanaged_keys:
            self += Purge(f"~/.ssh/{file_name_rsa}")

        if self.id_rsa_pub:
            self += File(f"~/.ssh/{file_name_rsa}.pub", content=self.id_rsa_pub)

        # ED25519
        if self.id_ed25519:
            self += File(
                f"~/.ssh/{file_name_ed25519}",
                content="{}\n".format(self.id_ed25519),
                mode=0o600,
                sensitive_data=True,
            )

        elif self.purge_unmanaged_keys:
            self += Purge(f"~/.ssh/{file_name_ed25519}")

        if self.id_ed25519_pub:
            self += File(f"~/.ssh/{file_name_ed25519}.pub", content=self.id_ed25519_pub)

        # ScanHost
        for host in self.scan_hosts:
            self += ScanHost(host)


class ScanHost(Component):
    """This component adds the host key of a provided host to the service
    user's known host file."""

    namevar = "hostname"
    known_hosts = "~/.ssh/known_hosts"
    port = 22

    def configure(self):
        self.known_hosts = self.map(self.known_hosts)
        self += File(
            os.path.dirname(self.known_hosts),
            ensure="directory",
            mode=0o700,
            leading=True,
        )

    def verify(self):
        if not os.path.exists(self.known_hosts):
            raise batou.UpdateNeeded()
        with open(self.known_hosts, "r") as f:
            content = f.read()
        if self.port == 22:
            match = self.hostname
        else:
            match = "[{}]:{}".format(self.hostname, self.port)
        if match not in content:
            raise batou.UpdateNeeded()

    def update(self):
        try:
            del os.environ["SSH_AUTH_SOCK"]
        except KeyError:
            pass

        v4_failed = v6_failed = None
        try:
            self.cmd(
                'ssh-keyscan -4 -p {} "{}" >> "{}"'.format(
                    self.port, self.hostname, self.known_hosts
                )
            )
        except batou.utils.CmdExecutionError as e_v4:
            v4_failed = e_v4
        try:
            self.cmd(
                'ssh-keyscan -6 -p {} "{}" >> "{}"'.format(
                    self.port, self.hostname, self.known_hosts
                )
            )
        except batou.utils.CmdExecutionError as e_v6:
            v6_failed = e_v6

        if v4_failed and v6_failed:
            raise RuntimeError(
                f"Could not scan host {self.hostname}\n"
                f"IPv4: {v4_failed}\n"
                f"IPv6: {v6_failed}\n",
                v4_failed,
                v6_failed,
            )
