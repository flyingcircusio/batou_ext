import glob
import os
import os.path
import shutil
import urllib.parse

import batou.component
import batou.lib.file
import batou.lib.git

import batou_ext.ssh


class SymlinkAndCleanup(batou.component.Component):
    """
    Symlink the give file or directory to `current`, symlink the file or directory that was symlinked to `current` to `last` and remove all files matching `pattern` that are not currently linked to current or last.
    This utility is mostly used for Git Checkouts, which can grow considerably in size, but may also be used for S3 File Downloads or other Folders and Files that should be cached.
    """

    namevar = "current"
    pattern = None
    _current_link = None
    _last_link = None

    prefix = None

    def configure(self):
        self._current_link = (
            f"{self.prefix}-current" if self.prefix else "current"
        )
        self._last_link = f"{self.prefix}-last" if self.prefix else "last"
        self.dir = os.path.dirname(self.current)
        self.current = os.path.basename(self.current)

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

        current = self._link(self._current_link)
        last = self._link(self._last_link)
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
            for el in self._list_removals():
                batou.output.annotate("Removing: {}".format(el))
                try:
                    if os.path.isdir(el):
                        shutil.rmtree(el)
                    else:
                        os.remove(el)
                except OSError as e:
                    batou.output.error(f'Failed to remove "{el}": {e.strerror}')
                    pass
