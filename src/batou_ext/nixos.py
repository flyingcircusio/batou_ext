import json
import os
from pathlib import Path
from typing import Optional

from batou.component import Component
from batou.lib.file import JSONContent, ManagedContentBase, Purge

import batou_ext.nix


class NixosModuleContent(ManagedContentBase):
    json_file: Optional[Component] = None

    def render(self):
        self.content = self.expand(
            """\
# this file is managed by batou, any manual changes will be overwritten by the next deployment
{pkgs, ...}@args: let
  component = builtins.fromJSON (builtins.readFile {{component.json_file.path}});
  module = (

{{component.content}}

  );
in {
  imports = [(module component)];
}
            """,
        )


@batou_ext.nix.rebuild
class NixOSModule(Component):
    namevar = "path"
    source_component: Optional[Component] = None

    def configure(self):
        basename = os.path.basename(self.path)

        self.json_file = JSONContent(
            self.map(basename.replace(".nix", "_component.json")),
            data=json.loads(
                json.dumps(
                    self.source_component or self.parent,
                    sort_keys=True,
                    indent=4,
                    default=lambda obj: {
                        attr: getattr(obj, attr)
                        for attr in dir(obj)
                        if not callable(getattr(obj, attr))
                        and not attr.startswith("_")
                        and not attr in ["sub_components", "parent", "timer"]
                        and not attr in dir(Component)
                    },
                )
            ),
        )
        self += self.json_file

        self.module_file = NixosModuleContent(
            os.path.join("/etc/local/nixos", basename),
            json_file=self.json_file,
            source=basename,
        )
        self += self.module_file


class PurgeNixOSModule(Component):
    namevar = "name"

    def configure(self):
        basename = os.path.basename(self.name)

        self += Purge(os.path.join("/etc/local/nixos", basename))
