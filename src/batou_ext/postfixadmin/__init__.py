from batou.component import Component
from batou_ext.postfixadmin.postfix import Postfix

class PostfixAdmin(Component):

    namevar = 'address'

    def configure(self):
        self += Postfix(self.address)
