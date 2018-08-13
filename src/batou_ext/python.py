import batou.component


class Pipenv(batou.component.component):
    """Sync pipenv

    Usage:

    * Checkout project to workdir, expecting Pipfile/Pipfile.lock there
    * self += Pipenv()`
    * Run services via `pipenv.executable` (points ot virualenv'ed python)

    Notes:

    * The Python version *is* specified in the Pipfile. So there is no need to
      pass.
    * `pipenv` is epxected to be there already. I.e. coming from the system.
    * For NixOS you can `nix-env -iA nixos.pipenv`. You will also need
      `nixos.which` and the python version the Pipfile specifies.

    """

    def configure(self):
        self.executable = self.expand('{{component.workdir}}/.venv/bin/python')

    def verify(self):
        self.assert_file_is_current(
            '.venv/bin/python',
            ['Pipfile', 'Pipfile.lock'])
        # Is this Python (still) functional 'enough'
        # from a setuptools/distribute perspective?
        self.assert_cmd('bin/python -c "import pkg_resources"')

    def update(self):
        self.cmd('rm -rf .venv')
        self.cmd('pipenv sync',
                 env={'PIPENV_VENV_IN_PROJECT': '1'})
