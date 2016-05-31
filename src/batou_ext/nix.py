import batou
import batou.component


class Package(batou.component.Component):
    """Install Nix package for user.

    Usage:

        self += batou_ext.nix.Package('pbzip2-1.1.12')

    """

    namevar = 'package'

    def verify(self):
        stdout, stderr = self.cmd('nix-env --query')
        if self.package not in stdout.splitlines():
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd('nix-env -i {}'.format(self.package))
