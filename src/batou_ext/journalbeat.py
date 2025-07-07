from importlib.resources import files

import batou.component
import batou.lib.file


class JournalBeatTransport(batou.component.Component):

    """A shortcut for sending logmessages via journalbeat to a centralised loghost."""

    nix_file_path = batou.component.Attribute(
        str, default="/etc/local/nixos/journalbeat.nix"
    )
    transport_name = batou.component.Attribute(str)
    graylog_host = batou.component.Attribute(str)
    graylog_port = batou.component.Attribute(int, default=12301)

    def configure(self):

        self += batou.lib.file.File(
            self.nix_file_path,
            content=(
                files(__spec__.parent) / "resources/journalbeat.nix"
            ).read_bytes(),
        )
