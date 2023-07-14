import hashlib
import os
import re
from typing import Optional

import pkg_resources
from batou import UpdateNeeded
from batou.component import Attribute, Component
from batou.lib.file import File
from batou.lib.service import Service

import batou_ext.nix


@batou_ext.nix.rebuild
class Container(Component):
    """
    A OCI Container component.
    With this component you can dynamically schedule docker containers to be run on the target host

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
    envfile: Optional[str] = None
    mounts: dict = {}
    ports: dict = {}
    env: dict = {}

    # secrets
    registry_address = Attribute(Optional[str], None)
    registry_user = Attribute(Optional[str], None)
    registry_password = Attribute(Optional[str], None)

    # internal use
    _specifier_pattern = r"^(?:(?P<registry>[^\/]+)\/)?(?P<container>[^:]+)(?::(?P<tag>[^\/]+))?$"
    _required_params_ = {
        "image": "mysql",
    }

    def configure(self):
        match = re.match(self._specifier_pattern, self.image)

        if match:
            spec_registry = match.group("registry")
            spec_containername = match.group("container")
            spec_tag = match.group("tag")

            # the image-provided registry addresss overrides the default one
            if spec_registry:
                self.registry_address = spec_registry

            # the container_name argument overrides the image-provided container specifier
            if not self.container_name:
                self.container_name = spec_containername.replace("/", "_")

            # spec version overrides the argument provided or default version
            if spec_tag:
                self.version = spec_tag
        else:
            raise RuntimeError(
                f"could not match the docker spec against the provided container image string: '{self.image}'"
            )

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

        self += File(
            f"/etc/local/nixos/docker_{self.container_name}.nix",
            sensitive_data=True,
            source=os.path.join(
                os.path.dirname(__file__), "resources/oci-template.nix"
            ),
        )

    def verify(self):
        local_digest, stderr = self.cmd(
            "docker image inspect {{component.image}} | jq -r 'first | .RepoDigests | first | split(\"@\") | last' || echo image not available locally"
        )
        remote_digest, stderr = self.cmd(
            "docker manifest inspect {{component.image}} -v | jq -r 'if type ==\"array\" then (. | first) else . end | .Descriptor.digest'"
        )

        if local_digest != remote_digest:
            raise UpdateNeeded()
