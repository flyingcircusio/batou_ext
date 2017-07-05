import batou.component
import copy
import json


def dict_merge(a, b):
    """recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and bhave a key who's value is a dict then dict_merge is called
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
        if current_data != self.config:
            raise batou.UpdateNeeded

    def update(self):
        with open(self.target, 'wb') as f:
            json.dump(self._config, f)
