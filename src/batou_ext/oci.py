import os
import shlex
from textwrap import dedent
from typing import Optional

import batou
from batou import UpdateNeeded
from batou.component import Attribute, Component
from batou.lib.file import File
from batou.utils import CmdExecutionError

import batou_ext.nix


@batou_ext.nix.rebuild
class Container(Component):
    """A OCI Container component.

    With this component you can dynamically schedule docker containers to be
    run on the target host.

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

    """

    # general options
    image = Attribute(str)
    version: str = "latest"
    container_name: Optional[str] = None

    # specific options
    entrypoint: Optional[str] = None
    docker_cmd: Optional[str] = None
    envfile: Optional[File] = None
    mounts: dict = {}
    ports: dict = {}
    env: dict = {}
    depends_on: list = None
    extra_options: list = None

    # secrets
    registry_address = Attribute(Optional[str], None)
    registry_user = Attribute(Optional[str], None)
    registry_password = Attribute(Optional[str], None)

    _required_params_ = {
        "image": "mysql",
    }

    # cache spanning multiple components deploying the same container
    _remote_manifest_cache = {}

    def configure(self):
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

        if not self.depends_on:
            self.depends_on = []

        self += File(
            f"/etc/local/nixos/docker_{self.container_name}.nix",
            sensitive_data=False,
            source=os.path.join(
                os.path.dirname(__file__), "resources/oci-template.nix"
            ),
        )

    def verify(self):
        self.assert_no_changes()
        self.envfile.assert_no_changes()

        valid = False

        container_image_id, stderr = self.cmd(
            dedent(
                """\
            docker container insepct {{component.container_name}} \
                | jq -r '.[0].Image'
                """
            )
        )
        local_image_id, stderr = self.cmd(
            dedent(
                """\
            docker image inspect {{component.image}}:{{component.version}} \
                | jq -r '.[0].Id' \
                || echo image not available locally
                """
            )
        )
        if local_image_id != container_image_id:
            # If the container is not running the image we expect, we need to
            # restart it. If its the same, we need to dig further
            error = (
                "Container is running different image. "
                "({container_image_id} vs. {local_image_id})"
            )
            local_digest, stderr = self.cmd(
                dedent(
                    """\
                docker image inspect {{component.image}}:{{component.version}} \
                    | jq -r 'first | .RepoDigests | first | split("@") | last' \
                    || echo image not available locally
                    """
                )
            )

            image_ident = f"{self.image}:{self.version}@{local_digest}"
            try:
                valid = self._remote_manifest_cache[image_ident]
                error = "(cached)"
            except KeyError:
                if self.registry_address:
                    logintxt, _ = self.cmd(
                        self.expand(
                            dedent(
                                """\
                docker login \\
                    {%- if component.registry_user and component.registry_password %}
                    -u {{component.registry_user}} \\
                    -p {{component.registry_password}} \\
                    {%- endif %}
                    {{component.registry_address}}
                """
                            )
                        )
                    )

                try:
                    stdout, stderr = self.cmd(
                        f"docker manifest inspect {image_ident}"
                    )
                except CmdExecutionError as e:
                    valid = False
                    error = e.stderr
                    if error.startswith(
                        "unsupported manifest format"
                    ):  # gitlab
                        batou.output.annotate(error, debug=True)
                        error = error[:50]
                else:
                    # `docker manifest inspect` silently raises an error,
                    # returns code 0 when unathorized
                    if stderr == "unauthorized":
                        raise RuntimeError(
                            "Wrong credentials for remote container registry"
                        )
                    valid = True
                self._remote_manifest_cache[image_ident] = valid

        if not valid:
            self.log("Update due digest verification error: %r", error)
            raise UpdateNeeded()

    def update(self):
        self.cmd(f"sudo systemctl restart docker-{self.container_name}")
