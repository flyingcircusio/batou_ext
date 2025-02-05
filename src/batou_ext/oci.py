import json
import os
import shlex
from textwrap import dedent
from typing import Dict, Optional

import batou
from batou import UpdateNeeded
from batou.component import Attribute, Component
from batou.lib.file import File
from batou.utils import CmdExecutionError

import batou_ext.nix


class PodmanRuntime(Component):
    """
    Marker to indicate that containers are running with podman instead of
    docker.

    The backend can only be set globally in NixOS, so this is done with a single,
    global component here.
    """

    def configure(self):
        self.provide("oci:podman", self)
        self += File(
            "/etc/local/nixos/oci-backend.nix",
            content=dedent(
                """\
        {
          virtualisation.podman.enable = true;
        }
        """
            ),
        )


class Container(Component):
    """A OCI Container component.

    With this component you can dynamically schedule docker or podman containers
    to be run on the target host.

    Note: the `podman` backend is still considered experimental and thus subject
    to change. Running both docker and podman containers on the same VM is currently
    not supported.

    Note: Docker image specifiers do not follow a properly resolvable pattern.
    Therefore, container registries have to be specified seperately if you need
    to log in before. If you do not provide a container registry, docker will
    use the default one for authentication. You can choose to also append the
    image attribute with the registry but this module will do so automatically.

    ```
    # the following two call are identical:
    self += batou_ext.oci.Container(
        image="foo",
        registry_address="test.registry",
        registry_user="foo",
        registry_password="bar")

    self += batou_ext.oci.Container(
        image="test.registry/foo",
        registry_address="test.registry",
        registry_user="foo",
        registry_password="bar")

    # However, this will fail since docker will try to log into the default container registry
    # with the provided credentials and then pull the image from the registry specified in the image string
    self += batou_ext.oci.Container(
        image="test.registry/foo",
        registry_user="foo",
        registry_password="bar")


    # if you don't need to authenticate, not explicitly specifying the registry is fine of course
    # and it will pull the image from the correct registry
    self += batou_ext.oci.Container(image="test.registry/foo")
    ```

    Example:
    ```
    self += batou_ext.oci.Container(image = "mysql", version = "8.0")
    ```

    If you have multiple containers on one machine you can consolidate the
    rebuild:

    ```
    self += batou_ext.oci.Container(
        image="mysql",
        version="8.0",
        rebuild=False,
    )
    container = self._
    # add more containers

    self += Rebuild()
    self += container.activate()
    ```

    Containers can use `podman` as backend by adding the `PodmanRuntime`
    component:
    ```
    self += batou_ext.oci.PodmanRuntime()
    self += batou_ext.oci.Container(
        image="mysql"
    )
    ```

    This assumes that the container has a healthcheck configured.
    The unit `podman-mysql` will remain in state `activating` until
    the container is in `healthy` state. Then, it's transitioned into
    `active` state.

    The `batou_ext.nix.Rebuild` component will wait until newly started
    and restarted units are `active`, i.e. it will wait until the container is
    up with `podman`.

    If a podman container doesn't have a healthcheck defined, it's possible to add
    one via this component. The command is passed `/bin/sh -c`:

    ```
    self += batou_ext.oci.PodmanRuntime()
    self += batou_ext.oci.Container(
        image="without-healthcheck",
        health_cmd="curl --fail localhost || exit 1"
    )
    ```

    Please note that the healthcheck is executed _inside_ the container, so
    the container above would require a `curl` installed.

    When using podman containers, the user running the container
    has lingering enabled, i.e. a long-running user session is started by
    logind (https://www.freedesktop.org/software/systemd/man/latest/loginctl.html#enable-linger%20USER%E2%80%A6).
    """

    # general options
    image = Attribute(str)
    version: str = "latest"
    container_name = Attribute(str)

    health_cmd = Attribute(str, None)
    user = Attribute(str, None)

    # Set up monitoring
    monitor: bool = True

    # Automatically rebuild after this component
    rebuild: bool = True

    # specific options
    entrypoint: Optional[str] = None
    docker_cmd: Optional[str] = None
    envfile: Optional[File] = None
    mounts: dict = {}
    ports: dict = {}
    env: dict = {}
    depends_on: list = None
    extra_options: list = []

    # secrets
    registry_address = Attribute(Optional[str], None)
    registry_user = Attribute(Optional[str], None)
    registry_password = Attribute(Optional[str], None)

    _required_params_ = {
        "container_name": "mysql-container",
        "image": "mysql",
    }

    def configure(self):
        self.backend = (
            "podman"
            if self.require("oci:podman", strict=False, host=self.host)
            else "docker"
        )

        if (
            self.registry_user or self.registry_password
        ) and not self.registry_address:
            self.log(
                "WARN: you might want to specify the registry explicitly"
                " unless you really intend to log into the default"
                " docker registry"
            )

        if (
            self.registry_address
            # This is for the strange case of index.docker.io where you have
            # to set the registry_address to `https://index.docker.io/v1/`
            and not self.registry_address.startswith("https://")
            and not self.image.startswith(self.registry_address)
        ):
            self.image = f"{self.registry_address}{'/' if not self.registry_address.endswith('/') else ''}{self.image}"

        if self.registry_password:
            self += File(
                "registry-password", mode=0o600, content=self.registry_password
            )
            self.password_file = self._

        if self.envfile is None:
            self += File(
                f"{self.container_name}_env",
                sensitive_data=True,
                content="""{% for key, value in component.env.items() | sort -%}
{{key}}={{value}}
{% endfor %}""",
            )
            self.envfile = self._

        if self.docker_cmd:
            self._docker_cmd_list = shlex.split(self.docker_cmd)

        if self.backend != "podman":
            for prop in ["user", "health_cmd"]:
                assert (
                    getattr(self, prop) is None
                ), f"Container '{self.container_name}' runs with Docker, so the '{prop}' option is not supported!"
        else:
            if self.health_cmd is not None:
                # `json.dumps` quotes the quoted string in a way that it can
                # be placed as valid string into a Nix expression.
                # The bash-quoting is done in the OCI module in NixOS.
                self.health_cmd = json.dumps(self.health_cmd)

            if self.user is None:
                self.user = self.host.service_user

        if not self.depends_on:
            self.depends_on = []

        self += File(
            f"/etc/local/nixos/docker_{self.container_name}.nix",
            sensitive_data=False,
            source=os.path.join(
                os.path.dirname(__file__), "resources/oci-template.nix"
            ),
        )

        if self.rebuild:
            self += batou_ext.nix.Rebuild()
            self += self.activate()
            self._activate_container = self._  # Test support

    def activate(self):
        """Return a component which actually activates the container."""
        return ContainerRestart(self)


class ContainerRestart(Component):
    """Helper component to restart container.

    This is separated from `Container` to be able to bundle the rebuild
    and subsequently restart the container.

    Note: a rebuild *must* happen after `Container` and before this component.

    """

    namevar = "container"

    # cache spanning multiple components deploying the same container
    # the values are bools indicating whether or not containers with
    # this specific digest are up to date
    _remote_manifest_cache: Dict[str, bool] = {}

    def verify(self):
        container = self.container

        # Only trigger restart if either file has been changed. A rebuild
        # will not restart the container.
        self._need_explicit_restart = container.envfile.changed or (
            container.registry_password and container.password_file.changed
        )
        container.assert_no_changes()
        container.envfile.assert_no_changes()

        # If we are past this point no sub components have been changed. If
        # an UpdateNeeded is raised we *do* need a restart
        self._need_explicit_restart = True

        # id of the running container
        container_image_id = self._get_running_container_image_id()

        # newest *locally* available id
        local_image_id = self._get_local_image_id()

        # If the container is not running the image we expect, we need to
        # restart it. This will also ensure the container is up-to-date locally
        # since the container's nix service is set to always pull.
        if local_image_id != container_image_id:
            self.log(
                "Container is running an older version than is locally "
                "available and needs to be restarted."
            )
            raise UpdateNeeded("Local version update.")

        # If the container is running the newest locally available image then
        # check if there is a newer version available remotely

        # query the local digest to compare against upstream
        local_digest = self._get_local_digest()

        image_ident = (
            f"{container.image}:{container.version}@{local_digest}"
            if self.container.backend == "docker"
            else f"{container.image}@{local_digest}"
        )

        # test whether the ident has been checked already
        if image_ident in self._remote_manifest_cache:
            if self._remote_manifest_cache[image_ident]:
                # the image is up to date -> does not need an update
                return
            raise UpdateNeeded("Cached remote version update.")

        if container.registry_address:
            self._docker_login()

        valid = self._validate_remote_image(image_ident)

        # add the validated ident to the cache so that components using the
        # same container # and same versions don't have to query the remote
        self._remote_manifest_cache[image_ident] = valid
        if not valid:
            raise UpdateNeeded("Remote version update.")

    def update(self):
        if self._need_explicit_restart:
            self.cmd(
                f"sudo systemctl restart {self.container.backend}-{self.container.container_name}"
            )

    def _get_running_container_image_id(self):
        """Get the image Id the container is currently running.

        If there is no container, return "null".
        """
        image_id, stderr = self.cmd(
            dedent(
                """\
            {{ component.container.backend }} container inspect {{component.container.container_name}} \
                | jq -r '.[0].Image'
                """
            )
        )
        return image_id

    def _get_local_image_id(self):
        """Return the id of the image we have downloaded.

        If there is no image, return "null" .
        """
        local_image_id, stderr = self.cmd(
            dedent(
                """\
            {{ component.container.backend }} image inspect {{component.container.image}}:{{component.container.version}} \
                | jq -r '.[0].Id' \
                || echo image not available locally
                """
            )
        )
        return local_image_id

    def _get_local_digest(self):
        local_digest, stderr = self.cmd(
            dedent(
                """\
            {{ component.container.backend }} image inspect {{component.container.image}}:{{component.container.version}} \
                | jq -r 'first | .RepoDigests | first | split("@") | last' \
                || echo image not available locally
                """
            )
        )
        return local_digest

    def _docker_login(self):
        self.cmd(
            self.expand(
                dedent(
                    """\
        {{ component.container.backend }} login \\
            {%- if component.container.registry_user and component.container.registry_password %}
            -u {{component.container.registry_user}} \\
            -p {{component.container.registry_password}} \\
            {%- endif %}
            {{component.container.registry_address}}
        """
                )
            )
        )

    def _validate_remote_image(self, image_ident):
        try:
            # check if the digest aligns with the remote image
            # if it does not, this command will throw an error
            stdout, stderr = self.cmd(
                f"{self.container.backend} manifest inspect {image_ident}"
            )
        except CmdExecutionError as e:
            error = e.stderr
            if error.startswith("unsupported manifest format"):  # gitlab
                error = (
                    "Local and remote digest are out of sync! "
                    "The container needs to be restarted."
                )
            batou.output.annotate(error, debug=True)
            valid = False
        else:
            # `docker manifest inspect` silently raises an error when unauthorized,
            # returns exit code 0
            if stderr == "unauthorized":
                raise RuntimeError(
                    "Wrong credentials for remote container registry"
                )
            valid = True
        return valid
