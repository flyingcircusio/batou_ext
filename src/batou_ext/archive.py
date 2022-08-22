import os.path

import batou.lib.archive


class SingleUntar(batou.lib.archive.Untar):
    """Extract archive *once*

    This is useful when the target dir contains a version number or revision.
    In this case we do not expect that extracting the archive again could do
    any changes, so we skip the file-by-file validation which speeds things
    up considerably.

    """

    _required_params_ = {"target": "."}

    def configure(self):
        super().configure()
        self._finish_marker = os.path.join(
            os.path.dirname(self.target),
            f".{os.path.basename(self.target)}.finished-extract",
        )

    def verify(self):
        assert os.path.exists(self.archive)
        # Verify that the target dir is newer than the archive on disk.
        self.assert_file_is_current(self.target, [self.archive])
        # Verify that there is a finish marker and it is newer than the arvive
        self.assert_file_is_current(self._finish_marker, [self.archive])

    def update(self):
        super().update()
        self.touch(self._finish_marker)
