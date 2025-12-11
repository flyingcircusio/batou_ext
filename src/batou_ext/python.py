import json
import os.path
import shlex
from glob import glob
from textwrap import dedent

import batou.lib.python
from batou.component import Attribute, Component, ConfigString
from batou.lib.file import File
from batou.utils import CmdExecutionError


class Pipenv(Component):
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
            self.assert_file_is_current(self.executable, ["Pipfile", "Pipfile.lock"])
            # Is this Python (still) functional 'enough'
            # from a setuptools/distribute perspective?
            self.assert_cmd(
                '{{component.executable}} -c "from importlib.resources import files"'
            )

    def update(self):
        with self.chdir(self.target):
            self.cmd("rm -rf .venv")
            self.cmd("pipenv sync", env={"PIPENV_VENV_IN_PROJECT": "1"})


class VirtualEnvRequirements(Component):
    """
    Installs a Python VirtualEnv with a given requirements.txt

    Usage::
        self += VirtualEnvRequirements(
            version='2.7',
            requirements_path='/path/to/my/requirements.txt')
    """

    version = Attribute(str, default="3.12")
    requirements_path = Attribute(str, ConfigString("requirements.txt"))

    # Shell script to be sourced before creating VirtualEnv and pip
    pre_run_script_path = None

    # Passing environmental variables to batou's cmd
    env = None

    # May pass pre-fabricated virtualenv
    venv = None

    pip_install_extra_args = Attribute(str, default="")
    """Extra arguments for `pip install`, e.g. `--no-deps`."""

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
        if self.pre_run_script_path:
            pre_run = f"source {self.pre_run_script_path} && "
        else:
            pre_run = ""
        for req in self.requirements_paths:
            self.cmd(
                f"{pre_run} {self.venv.python} -m pip install {self.pip_install_extra_args} --upgrade -r {req}",
                env=self.env,
            )


class FixELFRunPath(Component):
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

    path = Attribute(str)
    env_directory = Attribute(str)
    glob_patterns = Attribute(list, default=["**/*.so", "**/*.so.*"])
    patchelf_jobs = Attribute(int, default=4)
    recurse_env_dir = Attribute(bool, default=True)

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
        patchelf = f"nix run --impure --expr {patchelf_expr} -- patchelf --force-rpath"
        cmd = f"xargs -P {self.patchelf_jobs} {patchelf} {args_}"
        proc = self.cmd(cmd, communicate=False)

        stdout, stderr = proc.communicate(input=bytes("\n".join(paths) + "\n", "utf-8"))
        if proc.returncode != 0:
            raise CmdExecutionError(cmd, proc.returncode, stdout, stderr)


class BuildEnv(Component):
    """Build a (raw) python environment in NixOS.

    Example::

        self += File("python-env.nix")
        self += BuildEnv()
        self.nix_env = self._

        self += File("requirements.txt")
        self += VirtualEnvRequirements(
            version=self.nix_env.version,
            requirements_path=["requirements.txt"]
            venv=VirtualEnv(
                self.nix_env.version,
                executable=self.nix_env.executable,
            ),
            env=self.nix_env.environment_variables(),
        )
        self += FixELFRunPath(
            path=self.map(""), env_directory=f"{self.nix_env.env_dir}/lib"
        )

    The required nix-env file could look like this::

        {
          pkgs ? import <nixpkgs> { },
          lib ? pkgs.lib,
        }:
        let
          env = pkgs.buildEnv {
            name = "python-env";
            paths = with pkgs; [
              python312
              zlib
              # allows to link against a glibc that's compatible with the rest
              # of the package-set used in this env.
              gcc
              # Hacky workaround for unintuitivie buildEnv behavior: when explicitly
              # selecting an output (via `pkgs.foo.lib`), `extraOutputsToInstall` will
              # discard this selection and install the outputs listed in this attribute
              # instead 🫠
              (buildEnv {
                name = "libgcc";
                paths = [ libgcc ];
                extraOutputsToInstall = [ "lib" ];
              })
            ];
            extraOutputsToInstall = [ "dev" "out" ];
          };
        in env


    """

    version = "3"
    executable = None
    env_dir = None
    nix_file = "python-env.nix"

    def configure(self):
        self.env_dir = os.path.join(self.workdir, ".raw-python-env")
        self.executable = os.path.join(self.env_dir, f"bin/python{self.version}")

    def environment_variables(self):
        """Return dict of required environment variables to use the env."""

        def e(name, additional_value):
            additional_path = os.path.join(self.env_dir, additional_value)
            return (name, f"{additional_path}:{os.environ.get(name, '')}")

        return dict(
            (
                e("CPATH", "include"),
                e("CPLUS_INCLUDE_PATH", "include"),
                e("C_INCLUDE_PATH", "include"),
                e("INFOPATH", "info"),
                e("LIBEXEC_PATH", "lib/libexec"),
                e("LIBRARY_PATH", "lib"),
                e("PATH", "bin"),
                e("PKG_CONFIG_PATH", "lib/pkgconfig"),
            )
        )

    def verify(self):
        # assert_file_is_current() does not work here, because it follows
        # symlinks, making the env_dir being created in 1970.
        assert os.path.exists(self.env_dir)
        env_mtime = os.lstat(self.env_dir).st_mtime

        assert os.path.exists(self.nix_file)
        nix_mtime = os.lstat(self.nix_file).st_mtime

        assert env_mtime >= nix_mtime

        out, err = self.cmd(f"nix derivation show -f '{self.nix_file}'")
        derivation = json.loads(out)
        expected_store_path = list(derivation.values())[0]["outputs"]["out"]["path"]
        try:
            current_store_path = os.path.realpath(self.env_dir)
        except OSError:
            raise batou.UpdateNeeded()

        assert expected_store_path == current_store_path

    def update(self):
        self.cmd(f"nix-build {self.nix_file} -o {self.env_dir}")
