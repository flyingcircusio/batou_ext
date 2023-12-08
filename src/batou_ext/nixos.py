from pathlib import Path

from batou.component import Component
from batou.lib.file import Purge

from batou_ext.nix import NixFile, component_to_nix, nix_dict_to_nix

# XXX: error messages stemming from the "batouModule" are displayed with
# wrong location information, it shows the glue module instead of the actual
# module. Can we fix that somehow?
GLUE_MODULE_TEMPLATE = """\
{{ pkgs, ... }}@args:

with builtins;

let
  moduleArgs = (import {workdir}/{prefix}_generated_context.nix) // args;
  batouModule = import {workdir}/{name}.nix moduleArgs;
in
{{ imports = [ batouModule ]; }}
"""


class NixOSModuleContext(Component):

    source_component: Component = None
    prefix: str = None

    def configure(self):

        if self.source_component:
            component = self.source_component
        else:
            component = self.parent

        context = nix_dict_to_nix({"component": component_to_nix(component)})

        if self.prefix is None:
            self.prefix = component.__class__.__name__.lower()

        self += NixFile(
            f"{self.prefix}_generated_context.nix",
            content=context,
            format_nix_code=True,
        )


class NixOSModule(Component):

    namevar = "name"

    name: str
    path: Path = Path("/etc/local/nixos")
    context = None

    def configure(self):

        self += NixFile(f"{self.name}.nix")

        if self.context is None:
            if hasattr(self.parent, "nixos_context"):
                self.context = self.parent.nixos_context
            else:
                self.context = NixOSModuleContext(source_component=self.parent)
                self.parent.nixos_context = self.context
                self.parent += self.context

        self += NixFile(
            self.path / f"batou_{self.name}.nix",
            content=GLUE_MODULE_TEMPLATE.format(
                workdir=self.workdir, name=self.name, prefix=self.context.prefix
            ),
            format_nix_code=True,
        )


class PurgeNixOSModule(Purge):
    namevar = "name"

    name: str
    path: Path = Path("/etc/local/nixos")

    def configure(self):
        self.pattern = self.path / f"batou_{self.name}.nix"
        super().configure()
