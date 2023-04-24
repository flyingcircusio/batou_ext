import batou
import batou.component
import batou.lib.file
import passlib.handlers.sha2_crypt
import passlib.hash


class HTPasswd(batou.component.Component):

    _required_params_ = {"users": "user:pwd"}
    namevar = "path"
    users = ""

    def configure(self):
        users = []
        for line in self.users.split("\n"):
            line = line.strip()
            user, password = line.split(":")
            password = passlib.handlers.sha2_crypt.sha512_crypt.hash(password)
            users.append("{}:{}".format(user, password))
        self += batou.lib.file.File(self.path, content="\n".join(users))
