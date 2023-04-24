import batou.component


class NFS(batou.component.Component):
    """
    A component to help ensure you got access paths for NFS in sync
    for your deployment.

    Defaults are based on Flyingcircus' NixOS environment.
    """

    # Path where NFS on client is mounted on
    basepath = batou.component.Attribute(
        str, batou.component.ConfigString("/mnt/nfs/shared/")
    )

    # Path where NFS-share is located on the NFS server
    serverpath = batou.component.Attribute(
        str, batou.component.ConfigString("/srv/nfs/shared/")
    )

    def configure(self):
        self.provide("nfs", self)
