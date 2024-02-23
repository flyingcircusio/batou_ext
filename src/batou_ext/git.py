import os
import os.path
import urllib.parse

import batou.component
import batou.lib.file
import batou.lib.git

import batou_ext.ssh
from batou_ext.file import SymlinkAndCleanup


class GitCheckout(batou.component.Component):
    """
    Performing a git checkout via SSH and sync into a special folder to
    add customized files later on.

    Usage:
    The component is depending on SSH so it expects a SSH keypair you
    could provide via batou_ext.ssh.SSHKeyPair.

    Add GitCheckout-component to your custom component

    self.checkout = GitCheckout(
        git_clone_url='ssh://git@git.example.org:12345/example-repo.git',
        git_revision='1234567892134131313132231',
        git_target=self.map('checkout'),
        git_port=12345,
        exclude=('src/my.conf', '.gitingore', 'db/dump.sql'))
    self += self.checkout

    This will create a folder 'checkout/' inside your component as well
    as a folder prepared-1234567892134131313132231.

    Now you can add your custom config:

    self += batou.lib.file.File(
        '{}/src/my.conf'.format(self.checkout.prepared_path),
        content='nice=true')

    The option sync_parent_folder is allowing you to sync into a different
    folder than the current one.
    """

    _required_params_ = {
        "git_clone_url": "https://example.com/repos",
        "git_revision": "commit-hash",
        "git_target": ".",
    }
    git_host = None
    git_clone_url = None
    git_revision = None
    git_target = None
    git_port = None
    exclude = ()
    sync_parent_folder = None

    # Automatically scan the remote ssh hostkey (once)
    scan_host = True

    def configure(self):

        # We need to ensure to have a valid URL. Assuming URL with schema
        # should be valid.
        assert urllib.parse.urlparse(self.git_clone_url).scheme

        if self.scan_host:
            if not self.git_host:
                self.git_host = urllib.parse.urlparse(
                    self.git_clone_url
                ).hostname
            if not self.git_port:
                self.git_port = (
                    urllib.parse.urlparse(self.git_clone_url).port or 22
                )
            # Add remote host to known hosts
            self += batou_ext.ssh.ScanHost(self.git_host, port=self.git_port)

        # Check whether we need a SSH key
        if urllib.parse.urlparse(self.git_clone_url).scheme == "ssh":
            self.require("sshkeypair")

        # Get a recent checkout
        self += batou.lib.git.Clone(
            self.git_clone_url,
            revision=self.git_revision,
            target=self.git_target,
        )

        # Actually sync into a working copy where parent-component can
        # add custom files
        if self.sync_parent_folder:
            self.prepared_path = self.map(
                "{}/prepared-{}".format(
                    self.sync_parent_folder, self.git_revision
                )
            )
        else:
            self.prepared_path = self.map(
                "prepared-{}".format(self.git_revision)
            )
        self += batou.lib.file.Directory(self.prepared_path, leading=True)
        self += batou.lib.file.Directory(
            self.prepared_path,
            source=self.git_target,
            exclude=((".git",) + self.exclude),
        )

    def symlink_and_cleanup(self):
        return SymlinkAndCleanup(self.prepared_path, pattern="prepared-*")


class Commit(batou.component.Component):
    """Commit a file."""

    _required_params_ = {"message": "text"}
    namevar = "filename"
    message = None
    workingdir = "."
    author_name = "Batou"
    author_email = "batou@flyingcircus.io"

    def configure(self):
        assert self.message

    def verify(self):
        if self.has_changes():
            raise batou.UpdateNeeded()

    def update(self):
        with self.chdir(self.workingdir):
            self.cmd("git config user.email '{{component.author_email}}'")
            self.cmd("git config user.name '{{component.author_name}}'")
            self.cmd("git add {{component.filename}}")
            self.cmd(
                "git commit -m '{{component.message}}' {{component.filename}}"
            )

    def has_changes(self):
        with self.chdir(self.workingdir):
            stdout, stderr = self.cmd(
                "git status --porcelain {{component.filename}}"
            )
        return bool(stdout.strip())


class Remote(batou.component.Component):
    """
    Ensure that a git repository checkout out at `git_repo` has the origin
    `name` pointing to `url`.

    Usage::

        self += batou_ext.git.Remote(
            "/path/to/linux",
            name="upstream",
            url="ssh://git@github.com/torvalds/linux"
        )

    By default, the component aborts with an error if `git_repo` does not
    exist or is not a git repository. This is not always desirable, for
    instance when this is involved in migrating an existing `git_repo`
    to a new remote: then, this works fine for migration, but not when
    bootstrapping e.g. a new environment where `git_repo` doesn't exist
    yet.

    To solve that, it's possible to let the component do nothing if
    `git_repo` doesn't exist like this:

        self += batou_ext.git.Remote(
            "/path/to/linux",
            ignore_not_existing=True,
            # ...
        )
    """

    namevar = "git_repo"
    url = batou.component.Attribute(str)
    name = batou.component.Attribute(str, "origin")
    ignore_not_existing = batou.component.Attribute(bool, False)

    def verify(self):
        if not os.path.exists(self.git_repo):
            if self.ignore_not_existing:
                return
            else:
                raise ValueError(
                    f"batou_ext.git.Remote({self.git_repo}): path does not exist!"
                )
        elif not os.path.exists(f"{self.git_repo}/.git"):
            raise ValueError(
                f"batou_ext.git.Remote({self.git_repo}): not a git repository!"
            )

        with self.chdir(self.git_repo):
            stdout, _ = self.cmd(
                f"git remote get-url {self.name}", ignore_returncode=True
            )
            if self.url != stdout.strip():
                raise batou.UpdateNeeded()

    def update(self):
        with self.chdir(self.git_repo):
            stdout, _ = self.cmd("git remote")
            verb = "set-url" if self.name in stdout.splitlines() else "add"
            self.cmd(f"git remote {verb} {self.name} {self.url}")


class Push(batou.component.Component):
    """`git push` if there are outgoing changes."""

    workingdir = "."

    def verify(self):
        if self.has_outgoing_changesets():
            raise batou.UpdateNeeded()

    def update(self):
        with self.chdir(self.workingdir):
            self.cmd("git push")

    def has_outgoing_changesets(self):
        with self.chdir(self.workingdir):
            stdout, stderr = self.cmd("LANG=C git status")
        return "Your branch is ahead of" in stdout


class StopDeployOnLocalGitChange(batou.component.Component):
    """
    Helping to perform a git checkout to a target, that is not clean.

    batou.lib.git.Clone() might overwrite local changes inside target directory -- whereas you want to stop the process instead.

    Usage:
    The component can be used before perfoming the actual git clone:

        from batou.lib.git impot Clone
        from batou_ext.git import StopDeployOnLocalGitChange

        …
        target = "/my/target/path"
        self += StopDeployOnLocalGitChange(target)
        self += Clone(
            self.git_url,
            revision="01234567abcd",
            target=target)
    """

    namevar = "target"
    target = None

    def verify(self):
        if not os.path.exists(self.target):
            return
        if not os.path.exists(os.path.join(self.target, ".git")):
            return
        with self.chdir(self.target):
            stdout, stderr = self.cmd("git status --porcelain")
        changes = bool(stdout.strip())
        if changes:
            raise RuntimeError(f"Deployment aborted:\n{stdout}\n{stderr}")
