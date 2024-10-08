import os
import os.path
from glob import glob
from time import time

import batou.lib.archive
from batou.component import Attribute


class SingleUntar(batou.lib.archive.Untar):
    """Extract archive *once*

    This is useful when the target dir contains a version number or revision.
    In this case we do not expect that extracting the archive again could do
    any changes, so we skip the file-by-file validation which speeds things
    up considerably.

    """

    _required_params_ = {"target": "."}

    cleanup_markers_after_days = Attribute(int, default=None)

    def configure(self):
        super().configure()
        self._markers_to_unlink = []
        self._only_marker_cleanup = False
        self._finish_marker = os.path.join(
            os.path.dirname(self.target),
            f".{os.path.basename(self.target)}.finished-extract",
        )

    def verify(self):
        # If a deployment does this for a while, a lot of these markers accumulate.
        # If this attribute is set, cleanup all markers with an mtime older than
        # `cleanup_markers_after_days` days.
        if self.cleanup_markers_after_days:
            now = time()
            diff = now - self.cleanup_markers_after_days * 24 * 3600

            self._markers_to_unlink = [
                file
                for file in glob(self.map(".*.finished-extract"))
                if os.path.getmtime(file) < diff
            ]

        assert os.path.exists(self.archive)
        # Verify that the target dir is newer than the archive on disk.
        self.assert_file_is_current(self.target, [self.archive])
        # Verify that there is a finish marker and it is newer than the arvive
        self.assert_file_is_current(self._finish_marker, [self.archive])

        # If we got that far, we don't have to unpack again. But we should
        # clean up some old markers.
        self._only_marker_cleanup = True
        assert self._markers_to_unlink == []

    def update(self):
        if not self._only_marker_cleanup:
            super().update()
            self.touch(self.target)
            self.touch(self._finish_marker)

        for old_marker in self._markers_to_unlink:
            os.remove(old_marker)
