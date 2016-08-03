import batou
import batou.component
import batou.lib.file


class ACL(batou.component.Component):
    path = ''
    # A list of rules for setfacl. Each rule e.g. user::rwx needs to be
    # one element of the list.
    ruleset = []

    def update(self):
        proc = self.cmd('setfacl --set-file=- "{}"'.format(self.path),
                        communicate=False)
        outs, errs = proc.communicate(input='\n'.join(self.ruleset))

    def verify(self):
        proc = self.cmd(
            'getfacl -cpE {}'.format(self.path),
            communicate=False)
        outs, errs = proc.communicate()
        if outs.strip() != '\n'.join(self.ruleset):
            raise batou.UpdateNeeded
