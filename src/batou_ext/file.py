import glob
import os
import os.path
import shutil
import subprocess
import tempfile
import urllib.parse
from textwrap import dedent

import batou
import batou.component
import batou.lib.file
import batou.lib.git

import batou_ext.ssh


class SymlinkAndCleanup(batou.component.Component):
    """
    Symlink the give file or directory to `current`, symlink the file or directory that was symlinked to `current` to `last`
    and remove all files matching `pattern` that are not currently linked to current or last.
    This utility is mostly used for Git Checkouts, which can grow considerably in size, but may also be used for
    S3 File Downloads or other Folders and Files that should be cached.

    The files matching `pattern` are discarded of using the `DeploymentTrash` component.
    Under the hood it uses systemd's tmpfiles.

    ```python
    new_file = download("test-v1.0.tar.gz")
    # clean up a all downloaded versions but the last two
    self += SymlinkAndCleanup(new_file.path, pattern = "*.tar.gz")
    ```
    """

    namevar = "current"
    pattern = None
    etag_suffix = batou.component.Attribute(str, ".etag")
    _current_link = None
    _last_link = None

    prefix = None

    systemd_read_max_iops = 100
    systemd_write_max_iops = 100
    trashdir = None
    trash_config_file_name = batou.component.Attribute(str, default="trash.nix")

    ## DEPRECATED, do not use
    use_systemd_run_async_cleanup = False
    systemd_extra_args = None

    def configure(self):
        self._current_link = (
            f"{self.prefix}-current" if self.prefix else "current"
        )
        self._last_link = f"{self.prefix}-last" if self.prefix else "last"
        self.dir = os.path.dirname(self.current)
        self.current = os.path.basename(self.current)
        self += DeploymentTrash(
            read_iops_limit=self.systemd_read_max_iops,
            write_iops_limit=self.systemd_write_max_iops,
            trashdir=self.trashdir,
            file_name=self.trash_config_file_name,
        )
        self.trash = self._

        if self.use_systemd_run_async_cleanup:
            batou.output.annotate(
                "use_systemd_run_async_cleanup is deprecated and will be removed in a future release, please remove it",
                yellow=True,
            )

        if self.systemd_extra_args:
            batou.output.annotate(
                "systemd_extra_args is deprecated and will be removed in a future release, please remove it",
                yellow=True,
            )

    @staticmethod
    def _link(path):
        try:
            return os.readlink(path)
        except OSError:
            batou.output.error(f"Unable to read link: `{path}`")
            return None

    @staticmethod
    def remove(links, el):
        try:
            links.remove(el)
        except ValueError:
            pass

    def _list_removals(self):
        candidates = glob.glob(self.pattern)
        candidates.extend(glob.glob(self.pattern + self.etag_suffix))

        current = self._link(self._current_link)
        last = self._link(self._last_link)
        if current == self.current:
            # keep last+current
            self.remove(candidates, current)
            self.remove(candidates, last)
            if current is not None:
                self.remove(candidates, current + self.etag_suffix)
            if last is not None:
                self.remove(candidates, last + self.etag_suffix)
        else:
            # keep current + new current"
            self.remove(candidates, current)
            self.remove(candidates, self.current)
            if current is not None:
                self.remove(candidates, current + self.etag_suffix)
            if self.current is not None:
                self.remove(candidates, self.current + self.etag_suffix)

        return candidates

    def verify(self):
        with self.chdir(self.dir):
            if self._link(self._current_link) != self.current:
                raise batou.UpdateNeeded()
            if self._list_removals():
                raise batou.UpdateNeeded()

    def update(self):
        with self.chdir(self.dir):
            current = self._link(self._current_link)
            if current != self.current:
                try:
                    os.remove(self._current_link)
                except OSError as e:
                    batou.output.error(
                        f'Failed to remove link "{self._current_link}" ({current}): {e.strerror}'
                    )
                    pass

                try:
                    os.remove(self._last_link)
                except OSError as e:
                    last = self._link(self._last_link)
                    batou.output.error(
                        f'Failed to remove link "{self._last_link}" ({last}): {e.strerror}'
                    )
                    pass

                batou.output.annotate("current -> {}".format(self.current))
                os.symlink(self.current, self._current_link)
                if current:
                    batou.output.annotate("last -> {}".format(current))
                    os.symlink(current, self._last_link)

            candidates = self._list_removals()
            if not candidates:
                batou.output.annotate("Nothing to remove.")

            for c in candidates:
                batou.output.annotate(f"Removing: {candidates}")
                self.trash.discard(c)


class DeploymentTrash(batou.component.Component):
    """A trash folder that is regularly cleaned up by systemd's tmpfiles.

    Files and Folders can be moved in here for asynchronous deletion that is
    not tied to the deployment. Due to this component being commonly used to
    offload deleting very large files, it also supports adding IOPS limits.


    ```python
    def configure(self):
        self.trash = DeploymentTrash(read_iops_limit=250, write_iops_limit=250)
        self += self.trash

    def update(self):
        # files that are created here should not be part of the deployment but
        # rather a sideproduct for example a cache directory or build artefacts
        # that are generated by some script
        large_folder = do_something_that_generates_a_lot_of_byproducts()
        self.trash.discard(large_folder)

    ```
    """

    file_name = batou.component.Attribute(str, default="trash.nix")

    read_iops_limit = 100
    write_iops_limit = 100

    trashdir = None

    def configure(self):
        if not self.trashdir:
            self.trashdir = os.path.expanduser("~/.deployment-trash")

        self += batou.lib.file.File(self.trashdir, ensure="directory")
        self += batou.lib.file.File(
            f"/etc/local/nixos/{self.file_name}",
            content=dedent(
                """\
            {
              systemd.tmpfiles.rules = [
                "d {{component.trashdir}} 0755 - - 1h -"
              ];

              systemd.services."systemd-tmpfiles-clean".serviceConfig = {
                IOReadIOPSMax=["{{component.trashdir}} {{component.read_iops_limit}}"];
                IOWriteIOPSMax=["{{component.trashdir}} {{component.write_iops_limit}}"];
              };
            }
        """
            ),
        )

    def discard(self, path):
        target = tempfile.mkdtemp(dir=self.trashdir)
        try:
            os.rename(path, os.path.join(target, os.path.basename(path)))
        except FileNotFoundError:
            # Nothing to delete.
            pass
        except OSError as e:
            batou.output.annotate(
                "check that the deployment trash dir and the directory you want to trash are on the same device"
            )
            raise e
