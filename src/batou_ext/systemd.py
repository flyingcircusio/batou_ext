import pkg_resources
from batou.component import Attribute, Component
from batou.lib.file import File


class ScalableService(Component):
    """
    Configure a systemd unit that can have multiple equal instances, such
    as multiple consumers for a message queue.

    Usage::

        self += ScalableService("message-consumer", running_instances=5)
        self.unit_identifier = self._.unit_identifier
        self += File("/etc/local/nixos/message-consumer-settings.nix")
        self += Rebuild()

    With a `message-consumer-settings.nix` looking like this:

        {
          systemd.services."{{ component.unit_identifier }}" = {
            serviceConfig = {
              /* ExecStart etc. */
            };
          };
        }

    This creates a systemd target called `message-consumer.target`
    and a template service called `message-consumer@.service`. When
    the configuration gets activated, five instances of this service
    are started, namely `message-consumer@0.service` to
    `message-consumer@4.service`. When the machine gets rebooted,
    these five instances will be started automatically.

    The number of instances running by default can be changed with the
    `running_instances` attribute.

    Please note that the unit is completely empty and thus invalid. A rebuild
    must not happen before `message-consumer-settings.nix` in the example above
    is added that fully configures the service.

    If needed, more services from this template can be started like this:

        $ systemctl start message-consumer@{5..23}

    This starts 19 additional units.

    When running

        $ systemctl restart message-consumer.target

    all 24 running units will be restarted.

    When running

        $ systemctl stop message-consumer.target

    all 24 running units will be stopped.

    However, when running

        $ systemctl start message-consumer.target

    after that, only 5 units will get back up. The same applies to an
    additional deployment or a reboot of the VM.

    Hence, starting additional services is a temporary measure to quickly
    get more workers up. The change must be persisted in the deployment
    after that.
    """

    namevar = "base_name"
    running_instances = Attribute(int, 4)

    def configure(self):
        self += File(
            f"/etc/local/nixos/scale-{self.base_name}.nix",
            content=pkg_resources.resource_string(
                "batou_ext", "resources/scalable-service.nix"
            ),
        )

        self.unit_identifier = f"{self.base_name}@"
