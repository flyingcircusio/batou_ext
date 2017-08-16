import batou.component
import copy
import json
import re
import yaml


def dict_merge(a, b):
    """recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and b have a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.

    https://www.xormedia.com/recursively-merge-dictionaries-in-python/

    """
    if not isinstance(b, dict):
        return b
    result = copy.deepcopy(a)
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        elif k in result and isinstance(result[k], list):
            result[k] = result[k][:]
            result[k].extend(v)
        else:
            result[k] = copy.deepcopy(v)
    return result


class CustomizeJson(batou.component.Component):
    """Customize an existing JSON configuration.

    The given configuration will be merged with the source configuration.

    Usage::

        self += batou_ext.config.CustomizeJson(
            'target/config.json',
            source='source/config.json',
            config=dict(
                a=37,
                b=dict(c='foo')))

    """

    namevar = 'target'
    source = None
    config = None

    def configure(self):
        pass

    def _generate(self):
        with open(self.source) as f:
            data = json.load(f)
        return dict_merge(data, self.config)

    def verify(self):
        self._config = self._generate()
        try:
            with open(self.target) as f:
                current_data = json.load(f)
        except (IOError, ValueError):
            raise batou.UpdateNeeded
        if current_data != self._config:
            raise batou.UpdateNeeded

    def update(self):
        with open(self.target, 'wb') as f:
            json.dump(self._config, f)


class CustomizeYaml(batou.component.Component):
    """Customize an existing YAML configuration.

    The given configuration will be merged with the source configuration.

    Usage::

        self += batou_ext.config.CustomizeYaml(
            'target/config.yml',
            source='source/config.yml',
            config=dict(
                a=37,
                b=dict(c='foo')))

    """
    namevar = 'target'
    source = None
    config = None

    def configure(self):
        pass

    def _generate(self):
        with open(self.source) as f:
            data = yaml.load(f)
        return dict_merge(data, self.config)

    def verify(self):
        self._config = self._generate()
        try:
            with open(self.target) as f:
                current_data = yaml.load(f)
        except (IOError, ValueError):
            raise batou.UpdateNeeded
        if current_data != self._config:
            raise batou.UpdateNeeded

    def update(self):
        with open(self.target, 'wb') as f:
            yaml.dump(self._config, f)


class RegexPatch(batou.component.Component):
    """Patch existing file with a regexp.

    Usage::

        self += batou_ext_config.RegexPatch(
            '/path/to/file',
            pattern=r'^foo=\d+(\w+)',
            replacement=r'foo=27\1')

    """

    path = None
    namevar = 'path'
    pattern = None
    replacement = None

    def configure(self):
        self.pattern = re.compile(self.pattern, re.MULTILINE)

    def _patch(self):
        return self.pattern.sub(self.replacement, self.source)

    def verify(self):
        with open(self.path, 'r') as f:
            self.source = f.read()
        m = self.pattern.search(self.source)
        assert m, "Could not configure, no match for pattern: {}".format(
            self.pattern.pattern)
        if self.source != self._patch():
            raise batou.UpdateNeeded()

    def update(self):
        with open(self.path, 'w') as f:
            f.write(self._patch())


class MultiRegexPatch(batou.component.Component):
    """Patch existing file with multiple regexpt.

    Usage::

        self += batou_ext_config.MultiRegexPatch(
            '/path/to/file', patterns=[
            (r'pattern-to-match',
             r'value-to-replace-with'),

            (r'another-pattern',
             r'another-replacement'),
        ])

    """

    namevar = 'path'

    def configure(self):
        for pattern, replacement in self.patterns:
            self += batou.c.apo100.RegexPatch(
                self.path,
                pattern=pattern,
                replacement=self.parent.expand(replacement))
