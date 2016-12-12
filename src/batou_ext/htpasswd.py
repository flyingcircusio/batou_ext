import batou
import batou.component
import batou.lib.file
import passlib.hash.sha512_crypt

class HTPasswd(batou.component.Component):

    namevar = 'path'
    users = ''

    def configure(self):
        users = []
        for line in self.users.split('\n'):
            line = line.strip()
            user, password = line.split(':')
            password = passlib.hash.sha512_crypt.encrypt(password)
            users.append('{}:{}'.format(user, password))
        self += batou.lib.file.File(self.path, content='\n'.join(users))
