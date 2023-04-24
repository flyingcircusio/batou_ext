from batou.component import Component, platform

from batou_ext.postfixadmin.dovecot import PFADovecot
from batou_ext.postfixadmin.postfix import PFAPostfix


@platform("gocept.net", PFADovecot)
class PFADovecotFC(Component):
    def verify(self):
        self.parent.assert_no_changes()

    def update(self):
        self.cmd("sudo -n /etc/init.d/dovecot reload")


@platform("gocept.net", PFAPostfix)
class PFAPostfixFC(Component):
    def verify(self):
        self.parent.assert_no_changes()

    def update(self):
        self.cmd("sudo -n /etc/init.d/postfix restart")
