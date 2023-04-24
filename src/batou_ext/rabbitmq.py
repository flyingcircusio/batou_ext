"""RabbitMQ management.

Example::

    class RabbitMQ(batou.component.Component):

        erlang_cookie = None
        vhost = None
        username = None
        password = None

        def configure(self):
            self.provide('rabbitmq', self)
            self.address = batou.utils.Address(self.host.fqdn, 5672)
            self += ErlangCookie(cookie=self.erlang_cookie)
            self += PurgeUser('guest')
            self += VHost(self.vhost)
            self += User(
                self.username, password=self.password, tags=['management'])
            self += Permissions(
                self.username, permissions={self.vhost: ('.*', '.*', '.*')})

"""

import os
import stat

import batou
import batou.component
import batou.lib.file


class ErlangCookie(batou.component.Component):

    path = "~/.erlang.cookie"
    cookie = None

    def configure(self):
        self.path = self.map(self.path)
        self += batou.lib.file.Presence(self.path)

    def verify(self):
        try:
            with open(self.path, "r") as target:
                current = target.read()
                if current != self.cookie:
                    raise batou.UpdateNeeded()
            current = os.stat(self.path).st_mode
            if stat.S_IMODE(current) != 0o400:
                raise batou.UpdateNeeded()
        except FileNotFoundError:
            raise batou.UpdateNeeded()

    def update(self):
        os.chmod(self.path, 0o600)
        with open(self.path, "w") as target:
            target.write(self.cookie)
        os.chmod(self.path, 0o400)


class VHost(batou.component.Component):

    namevar = "name"
    name = None

    def verify(self):
        stdout, stderr = self.cmd("rabbitmqctl -q list_vhosts")
        vhosts = stdout.splitlines()
        if self.name not in vhosts:
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd("rabbitmqctl add_vhost {{component.name}}")


class Permissions(batou.component.Component):

    namevar = "username"
    username = None
    permissions = None

    def verify(self):
        stdout, stderr = self.cmd(
            "rabbitmqctl -q list_user_permissions {{component.username}}"
        )
        lines = stdout.splitlines()
        to_validate = self.permissions.copy()
        self.to_update = []
        self.to_delete = []
        for line in lines:
            if not line or line == "vhost\tconfigure\twrite\tread":
                # Table header. This used to be hidden with `-q` but was
                # moved to `-s` in recent rabbit mq versions. Alas old
                # versions don't support `-s`. So filter manually.
                continue
            vhost, conf, write, read = line.split("\t", 3)
            perms = to_validate.pop(vhost, None)
            if perms is None:
                self.to_delete.append(vhost)
            elif perms != (conf, write, read):
                self.to_update.append(vhost)
        self.to_update.extend(list(to_validate.keys()))
        if self.to_update or self.to_delete:
            raise batou.UpdateNeeded()

    def update(self):
        for vhost in self.to_delete:
            self.cmd(
                self.expand(
                    "rabbitmqctl clear_permissions"
                    " -p {{vhost}} {{component.username}}",
                    vhost=vhost,
                )
            )
        for vhost in self.to_update:
            conf, write, read = self.permissions[vhost]
            self.cmd(
                self.expand(
                    "rabbitmqctl set_permissions"
                    " -p {{vhost}} {{component.username}}"
                    " '{{conf}}' '{{write}}' '{{read}}'",
                    vhost=vhost,
                    conf=conf,
                    write=write,
                    read=read,
                )
            )


class User(batou.component.Component):
    """Create rabbitmq user."""

    _required_params_ = {
        "tags": (),
    }
    namevar = "username"
    username = None
    password = None
    tags = None

    def configure(self):
        self.tags = sorted(self.tags)
        self.tags_str = " ".join(self.tags)

    def verify(self):
        stdout, stderr = self.cmd("rabbitmqctl -q list_users")
        users = stdout.splitlines()
        self.create = True
        self.set_tags = True
        for line in users:
            if not line or line.startswith("user\t"):
                continue
            user, tags = line.split("\t", 1)
            tags = sorted(tags[1:-1].split(", "))
            if user == self.username:
                self.create = False
                if tags == self.tags:
                    self.set_tags = False
                break
        if self.create or self.set_tags:
            raise batou.UpdateNeeded()

    def update(self):
        if self.create:
            self.cmd(
                "rabbitmqctl add_user"
                " '{{component.username}}' '{{component.password}}'"
            )
        if self.set_tags:
            self.cmd(
                "rabbitmqctl set_user_tags"
                " {{component.username}} {{component.tags_str}}"
            )


class PurgeUser(batou.component.Component):

    namevar = "username"
    username = None

    def verify(self):
        stdout, stderr = self.cmd("rabbitmqctl -q list_users")
        users = stdout.splitlines()
        for line in users:
            if not line or line.startswith("user\t"):
                continue
            user, tags = line.split("\t", 1)
            if user == self.username:
                raise batou.UpdateNeeded()

    def update(self):
        self.cmd("rabbitmqctl delete_user {{component.username}}")
