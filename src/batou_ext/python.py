import batou.component
import os.path


class Pipenv(batou.component.Component):
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

    target = None

    def configure(self):
        if self.target is None:
            self.target = self.workdir
        self.venv = os.path.join(self.workdir, self.target, '.venv')
        self.executable = os.path.join(self.venv, 'bin/python')

    def verify(self):
        with self.chdir(self.target):
            self.assert_file_is_current(
                self.executable,
                ['Pipfile', 'Pipfile.lock'])
            # Is this Python (still) functional 'enough'
            # from a setuptools/distribute perspective?
            self.assert_cmd(
                '{{component.executable}} -c "import pkg_resources"')

    def update(self):
        with self.chdir(self.target):
            self.cmd('rm -rf .venv')
            self.cmd('pipenv sync',
                     env={'PIPENV_VENV_IN_PROJECT': '1'})
