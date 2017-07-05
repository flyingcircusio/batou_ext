import batou.component
import batou.lib.file
import batou.lib.git
import batou_ext.ssh
import glob
import os
import shutil


class GitCheckout(batou.component.Component):
    """
    Performing a git checkout via SSH and sync into a special folder to
    add customized files later on.

    Usage:
    The component is depending on SSH so it expects a SSH keypair you
    could provide via batou_ext.ssh.SSHKeyPair.

    Add GitCheckout-component to your custom component

    self.checkout += GitCheckout(
        git_host = 'git.example.org',
        git_clone_url = 'git@git.example.org:12345/example-repo.git',
        git_revision = '1234567892134131313132231',
        git_target = self.map('checkout'),
        git_port = 12345,
        exclude=('src/my.conf', '.gitingore', 'db/dump.sql'))
    self += self.checkout

    This will create a folder 'checkout/' inside your component as well
    as a folder prepared-1234567892134131313132231.

    Now you can add your custom config:

    self += batou.lib.file.File(
        '{}/src/my.conf'.format(self.checkout.prepared_path),
        content='nice=true')
    """
    git_host = None
    git_clone_url = None
    git_revision = None
    git_target = None
    git_port = None
    exclude = ()

    def configure(self):
        # We need a SSH key
        self.require('sshkeypair')

        # Add remote host to known hosts
        self += batou_ext.ssh.ScanHost(self.git_host)

        # Get a recent checkout
        self += batou.lib.git.Clone(
            self.git_clone_url,
            revision=self.git_revision,
            target=self.git_target)

        # Actually sync into a working copy where parent-component can
        # add custom files
        self.prepared_path = self.map('prepared-{}'.format(self.git_revision))
        self += batou.lib.file.Directory(self.prepared_path)
        self += batou.lib.file.Directory(
            self.prepared_path,
            source=self.git_target,
            exclude=(('.git',) + self.exclude)
        )

    def symlink_and_cleanup(self):
        return SymlinkAndCleanup(self.prepared_path)


class SymlinkAndCleanup(batou.component.Component):

    namevar = 'current'
    pattern = 'prepared-*'

    def configure(self):
        self.dir = os.path.dirname(self.current)
        self.current = os.path.basename(self.current)

    @staticmethod
    def _link(path):
        try:
            return os.readlink(path)
        except OSError:
            return None

    @staticmethod
    def remove(l, el):
        try:
            l.remove(el)
        except ValueError:
            pass

    def _list_removals(self):
        candidates = glob.glob(self.pattern)

        current = self._link('current')
        last = self._link('last')
        if current == self.current:
            # keep last+current
            self.remove(candidates, current)
            self.remove(candidates, last)
        else:
            # keep current + new current"
            self.remove(candidates, current)
            self.remove(candidates, self.current)

        return candidates

    def verify(self):
        with self.chdir(self.dir):
            if self._link('current') != self.current:
                raise batou.UpdateNeeded()
            if self._list_removals():
                raise batou.UpdateNeeded()

    def update(self):
        with self.chdir(self.dir):
            current = self._link('current')
            if current != self.current:
                try:
                    os.remove('current')
                except OSError:
                    pass
                try:
                    os.remove('last')
                except OSError:
                    pass
                batou.output.annotate('current -> {}'.format(self.current))
                os.symlink(self.current, 'current')
                if current:
                    batou.output.annotate('last -> {}'.format(current))
                    os.symlink(current, 'last')
            for el in self._list_removals():
                batou.output.annotate('Removing: {}'.format(el))
                try:
                    shutil.rmtree(el)
                except OSError:
                    pass
