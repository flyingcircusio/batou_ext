import os.path
import shlex
from glob import glob
from textwrap import dedent

import batou.component
import batou.lib.python
from batou.utils import CmdExecutionError


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
        self.venv = os.path.join(self.workdir, self.target, ".venv")
        self.executable = os.path.join(self.venv, "bin/python")

    def verify(self):
        with self.chdir(self.target):
            self.assert_file_is_current(
                self.executable, ["Pipfile", "Pipfile.lock"]
            )
            # Is this Python (still) functional 'enough'
            # from a setuptools/distribute perspective?
            self.assert_cmd(
                '{{component.executable}} -c "from importlib.resources import files"'
            )

    def update(self):
        with self.chdir(self.target):
            self.cmd("rm -rf .venv")
            self.cmd("pipenv sync", env={"PIPENV_VENV_IN_PROJECT": "1"})


class VirtualEnvRequirements(batou.component.Component):
    """
    Installs a Python VirtualEnv with a given requirements.txt

    Usage::
        self += VirtualEnvRequirements(
            version='2.7',
            requirements_path='/path/to/my/requirements.txt')
    """

    version = batou.component.Attribute(str, default="2.7")
    requirements_path = batou.component.Attribute(
        str, batou.component.ConfigString("requirements.txt")
    )

    # Shell script to be sourced before creating VirtualEnv and pip
    pre_run_script_path = None

    # Passing environmental variables to batou's cmd
    env = None

    # May pass pre-fabricated virtualenv
    venv = None

    def configure(self):

        if isinstance(self.requirements_path, str):
            self.requirements_paths = [self.requirements_path]
        elif isinstance(self.requirements_path, list):
            self.requirements_paths = self.requirements_path
        else:
            raise RuntimeError("Needs to be either string or list")

        if self.venv is None:
            self.venv = batou.lib.python.VirtualEnv(self.version)
        self += self.venv

    def verify(self):
        self.assert_no_changes()
        self.parent.assert_no_changes()

    def update(self):
        for req in self.requirements_paths:
            if self.pre_run_script_path:
                self.cmd(
                    (
                        "source {} && {} " "-m pip install --upgrade -r {}"
                    ).format(self.pre_run_script_path, self.venv.python, req),
                    env=self.env,
                )
            else:
                self.cmd(
                    "{} -m pip install --upgrade -r {}".format(
                        self.venv.python, req
                    ),
                    env=self.env,
                )


class FixELFRunPath(batou.component.Component):
    """
    Patches DT_RUNPATH & DT_RPATH of each shared object to either point to a
    given user env or a path relative to the shared object. Should only be used
    in conjunction with a virtual env with prebuilt binaries.

    Usage::
        self += FixELFRunPath(
            path="/path/to/venv",
            env_directory=os.path.expanduser('~/.nix-profile/lib')
        )

    Now each .so contains a DT_RPATH with

    * `~/.nix-profile/lib`: in this environment are external libraries of
      prebuilt binaries used by Python libraries. For instance a `libz.so`
      for `numpy`.

      Please keep in mind that each library in this environment will be used
      by the venv since DT_RPATH has the highest priority (over LD_LIBRARY_PATH
      and DT_RUNPATH).

    * `~/.nix-profile/lib/*` for each `*` that contains a shared object. This is
      necessary for e.g. libmysqlclient / libmariadb.so.3 which is in a subdir of
      `$out/lib`.

      This behavior can be turned off by setting `recurse_env_dir` to `False`.

    * `$ORIGIN/../foo.libs`. With this path, libraries relative to the
      shared library's path will be loaded. For instance, numpy
      installs `numpy.libs` with a few prebuilt libraries such as gfortran
      into a path relative its own libraries in the venv.

    Additional notes::

    * in the end it turned out to be necessary to use `DT_RPATH` instead of
      `DT_RUNPATH` for two reasons:

      * `numpy` among others expects `$ORIGIN/../../numpy.libs` to be in
        `DT_RPATH` since that is used for the library itself _and_ all other
        libraries below in the dependency tree (in contrast to DT_RUNPATH).

      * it's impossible to use both `DT_RPATH` and `DT_RUNPATH` for a single
        ELF binary since `DT_RPATH` will be ignored if `DT_RUNPATH` exists
        (see `ld.so(8)`).

      Despite the higher priority this is still preferable over
      `LD_LIBRARY_PATH` because it doesn't "infect" the entire process: the
      env gets inherited to child processes and causes side-effects there as
      well (see e.g. FC-35412, FC-36567). Also, DT_RPATH will only be used
      for the child dependencies of a binary. That means that it will be used
      for each library loaded by numpy's C libraries, but won't be used for e.g.
      psycopg2 and its libraries.

    * It's not desirable to use `glibc` inside an env used by this component:

      * It's still very easy to run into ABI issues: for instance for development
        I put a glibc <2.34 into the user env which still had a non-empty
        libpthread.so.0 (got merged into libc.so.6 in 2.34) which caused
        caused a conflict with how the newer glibc is structued.

      * Generally when using a recent Python and a recent e.g. numpy, there's
        a good chance it was linked against a relatively new glibc and
        providing an old glibc here will break.

      * When using psycopg2 (as opposed to psycopg2-binary), the library
        will be compiled on install. For that, it's better to install `gcc` into
        a user env to make sure that this is used as C compiler.
        Subsequently, it ensures that the correct glibc is provided on linking.
    """

    path = batou.component.Attribute(str)
    env_directory = batou.component.Attribute(str)
    glob_patterns = batou.component.Attribute(
        list, default=["**/*.so", "**/*.so.*"]
    )
    patchelf_jobs = batou.component.Attribute(int, default=4)
    recurse_env_dir = batou.component.Attribute(bool, default=True)

    def verify(self):
        self.assert_no_changes()
        self.parent.assert_no_changes()

    def update(self):
        if self.recurse_env_dir:
            with self.chdir(self.env_directory):
                directories = ":".join(
                    sorted(
                        {
                            self.env_directory + "/" + os.path.dirname(so_file)
                            for so_file in glob("**/*.so", recursive=True)
                        }
                    )
                )
        else:
            directories = self.env_directory

        with self.chdir(self.path):
            files_to_fix = [
                x
                for pattern in self.glob_patterns
                for x in glob(pattern, recursive=True)
            ]
            if not files_to_fix:
                return

            # add user env to DT_RPATH
            # & drop everything from DT_RPATH except self.env_directory
            # and directories in the venv (to allow shared libraries from numpy
            # to load other shared libraries from numpy).
            self.__patchelf(
                [
                    "--add-rpath-and-shrink",
                    directories,
                    "--allowed-rpath-prefixes",
                    f"{directories}:$ORIGIN",
                ],
                files_to_fix,
            )

    def __patchelf(self, args, paths):
        # The idea behind the `pkgs.patchelf-venv or` is to move the expression
        # into fc-nixos eventually to not rebuild patchelf on-demand (not too urgent though
        # since the patchelf build is relatively small).
        # If the patch gets accepted upstream, we should remove the entire dance here. If not,
        # the platform approach will be taken.
        patchelf_expr = shlex.quote(
            dedent(
                """
        with import <nixpkgs> {}; {
          patchelf = pkgs.patchelf-venv or patchelf.overrideAttrs ({ patches ? [], ... }: {
            patches = patches ++ [
              (fetchpatch {
                url = "https://github.com/flyingcircusio/patchelf/commit/6ffde887d77275323c81c2e091891251b021abb3.patch";
                hash = "sha256-4Qct2Ez3v6DyUG26JTWt6/tkaqB9h1gYaoaObqhvFS8=";
              })
            ];
          });
        }
        """
            )
        )

        args_ = " ".join(shlex.quote(arg) for arg in args)
        # `--force-rpath` because we need `rpath` for $ORIGIN since rpath
        # works for all ELFs below in the dependency tree in contrast to DT_RUNPATH.
        # It's impossible to use both at the same time because DT_RPATH will always
        # be ignored then. For more context, see `ld.so(8)`.
        patchelf = (
            f"nix run --impure --expr {patchelf_expr} -- patchelf --force-rpath"
        )
        cmd = f"xargs -P {self.patchelf_jobs} {patchelf} {args_}"
        proc = self.cmd(cmd, communicate=False)

        stdout, stderr = proc.communicate(
            input=bytes("\n".join(paths) + "\n", "utf-8")
        )
        if proc.returncode != 0:
            raise CmdExecutionError(cmd, proc.returncode, stdout, stderr)
