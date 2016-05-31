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


class Rebuild(batou.component.Component):
    """Trigger rebuild on FC platform.

    Usage::

        # Tirgger rebuild if self or subcomponent changed
        self += batou_ext.nix.Rebuild()

        # Trigger rebuild if specific components changed:
        self += batou_ext.nix.Rebuild(dependencies=(self, foo, bar))

    """

    dependencies = None

    def verify(self):
        if self.dependencies:
            for dependency in self.dependencies:
                dependency.assert_no_changes()
        else:
            self.parent.assert_no_subcomponent_changes()

    def update(self):
        self.cmd('sudo systemctl start fc-manage')
