import copy
import os.path
import re

import batou.component


def dict_merge(a, b):
    """recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and b have a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.
    https://www.xormedia.com/recursively-merge-dictionaries-in-python/
    """
    if not isinstance(b, dict):
        return b
    result = copy.deepcopy(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        elif k in result and isinstance(result[k], list):
            result[k] = result[k][:]
            result[k].extend(v)
        else:
            result[k] = copy.deepcopy(v)
    return result


class RegexPatch(batou.component.Component):
    r"""Patch existing file with a regexp.

    Usage::

        self += batou_ext.config.RegexPatch(
            '/path/to/file',
            pattern=r'^foo=\d+(\w+)',
            replacement=r'foo=27\1')

    If you don't want to patch inplace:

        self += batou_ext.config.RegexPatch(
            '/path/to/file',
            source='/path/to/some/file/'
            pattern=r'^foo=\d+(\w+)',
            replacement=r'foo=27\1')

    """

    _required_params_ = {
        "pattern": "pattern",
    }
    path = None
    namevar = "path"

    source = None
    pattern = None
    replacement = None

    def configure(self):
        self.pattern = re.compile(self.pattern, re.MULTILINE)

        if not self.path:
            raise ValueError("`path` must be set.")

        if not self.source:
            self.source = self.path

    def _patch(self):
        return self.pattern.sub(self.replacement, self._source_data)

    def verify(self):

        if not os.path.exists(self.source):
            # During predict, the file might not exist.
            raise batou.UpdateNeeded()
        with open(self.source, "r") as f:
            self._source_data = f.read()

        if not os.path.exists(self.path):
            # During predict, the file might not exist.
            raise batou.UpdateNeeded()
        with open(self.path, "r") as f:
            self._target_data = f.read()

        m = self.pattern.search(self._source_data)
        assert m, "Could not configure, no match for pattern: {}".format(
            self.pattern.pattern
        )
        if self._target_data != self._patch():
            raise batou.UpdateNeeded()

    def update(self):
        if not os.path.exists(self.source):
            raise IOError("The file to be patched does not exist:", self.source)

        if self._source_data is None:
            raise RuntimeError(
                "The file to be patched seems to have no valid content:",
                self.source,
            )

        with open(self.path, "w") as f:
            f.write(self._patch())


class MultiRegexPatch(batou.component.Component):
    """Patch existing file with multiple regexp.

    Usage::

        self += batou_ext.config.MultiRegexPatch(
            '/path/to/file', patterns=[
            (r'pattern-to-match',
             r'value-to-replace-with'),

            (r'another-pattern',
             r'another-replacement'),
        ])

    """

    namevar = "path"
    patterns = ()

    def configure(self):
        for pattern, replacement in self.patterns:
            self += RegexPatch(
                self.path,
                pattern=pattern,
                replacement=self.parent.expand(replacement),
            )
