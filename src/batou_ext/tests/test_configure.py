import importlib
import pkgutil
from typing import List
from unittest.mock import Mock

from batou.component import Component

import batou_ext


def find_components_in(path, parents=()) -> List[object]:
    """Find the classes deriving from batou.component.Component in a module.

    Return a list containing the classes.
    """
    classes = []
    modules = pkgutil.iter_modules(path)
    for _, name, ispkg in modules:
        if name == 'tests':
            continue

        dotted_path = ['batou_ext']
        dotted_path.extend(parents)
        dotted_path.append(name)

        module = importlib.import_module('.'.join(dotted_path))
        if ispkg:
            classes.extend(
                find_components_in(
                    module.__path__, parents=parents + (name, )))

        for name in dir(module):
            obj = getattr(module, name)
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, Component):
                continue
            if obj.__module__.startswith('batou.lib.'):
                # Omit from imports of classes from batou.lib.*
                continue
            classes.append(obj)

    return classes


def pytest_generate_tests(metafunc):
    """Generate a test for each component."""
    classes = find_components_in(batou_ext.__path__)
    idlist = [dotted_name(x) for x in classes]
    argvalues = [(x, ) for x in classes]

    metafunc.parametrize(('component', ),
                         argvalues,
                         ids=idlist,
                         scope="function")


def dotted_name(cls):
    return f'{cls.__module__}.{cls.__name__}'


class MockPostfixProvider(Component):
    """Mock component providing the expectations of postfix components."""

    address = Mock()
    connect = Mock()
    crt_file = Mock()
    database = Mock()
    dbms = Mock()
    key_file = Mock()
    password = Mock()
    username = Mock()

    def configure(self):
        self.provide('keypair::mail', self)
        self.provide('pfa::database', self)
        self.provide('postfix', self)
        self.provide('postgres', self)


class MockRoundcubeProvider(Component):
    """Mock component providing the expectations of roundcube components."""

    address = Mock()
    connect = Mock()
    database = Mock()
    dbms = Mock()
    password = Mock()
    username = Mock()

    def configure(self):
        self.provide('postfix', self)
        self.provide('postgres', self)
        self.provide('roundcube::database', self)


def test_prepare(root, mocker, component):
    """Assert that the `prepare` method of most components can be called.

    prepare itself calls the `configure` method.
    """
    mocker.patch('socket.gethostbyname', return_value='localhost')
    args = ('namevar', ) if component.namevar else ()
    required = getattr(component, '_required_params_', None)
    kw = required if required else {}
    instance = component(*args, **kw)
    component_name = dotted_name(component)
    if component_name in {
            # expecting parent component to have a `crontab` attribute:
            'batou_ext.nix.InstallCrontab', }:
        root.crontab = 'crontab'
    elif component_name in {
            # expecting a service user to be set and a `logrotate_conf`:
            'batou_ext.nix.LogrotateIntegration', }:
        root.environment.service_user = 'service'
        root.logrotate_conf = Mock()
        root.logrotate_conf.content = 'logrotate_conf content'
    elif component_name in {
            # expecting `executable`, `systemd`, and `checksum` attributes on
            # parent:
            'batou_ext.nix.UserInit', }:
        root.executable = 'my_script'
        root.systemd = {}
        root.checksum = 42
    elif component_name in {
            # expecting that some objects can be required:
            'batou_ext.postfixadmin.dovecot.PFADovecot',
            'batou_ext.postfixadmin.postfix.PFAPostfix',
            'batou_ext.postfixadmin.postgres.PFADatabase',
            'batou_ext.postfixadmin.PFA', }:
        MockPostfixProvider().prepare(root)
    elif component_name in {
            # expecting that some objects can be required:
            'batou_ext.roundcube.postgres.RoundcubeDatabase',
            'batou_ext.roundcube.Roundcube', }:
        MockRoundcubeProvider().prepare(root)
    elif component_name in {
            # expecting to be able to connect to Amazon S3 with actual
            # credentials:
            'batou_ext.s3.S3', }:
        mocker.patch('boto3.resource')

    instance.prepare(root)
