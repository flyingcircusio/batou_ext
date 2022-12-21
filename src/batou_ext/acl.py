import difflib

import batou
from batou.component import Attribute, Component


class ACL(Component):
    """Replace a file's ACL."""

    path = ""
    namevar = "path"

    # The complete new ACL. See `getfacl <filename>` for the format.
    ruleset = Attribute(list)  # of str

    def update(self):
        rules = "\n".join(self.ruleset).encode("UTF-8")
        proc = self.cmd(
            f"setfacl --set-file=- '{self.path}'",
            communicate=False,
        )
        outs, errs = proc.communicate(input=rules)
        if proc.returncode > 0:
            raise ValueError(f"setfacl error: {errs}")

    def verify(self):
        proc = self.cmd(f"getfacl -cpE '{self.path}'", communicate=False)
        outs, errs = proc.communicate()
        outs = outs.decode("UTF-8", errors="replace").strip()
        current_rules = sorted(outs.strip().split("\n"))
        if current_rules != sorted(self.ruleset):
            d = difflib.Differ()
            l1 = "\n".join(current_rules).splitlines()
            l2 = "\n".join(sorted(self.ruleset)).splitlines()
            result = d.compare(l1, l2)
            self.log("Updating ACL, diff:\n" + "\n".join(result))

            raise batou.UpdateNeeded
