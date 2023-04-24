import batou.component
import batou.lib.file
import pkg_resources


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
            content=pkg_resources.resource_string(
                __name__, "resources/journalbeat.nix"
            ),
        )
