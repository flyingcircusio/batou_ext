from ..file import DeploymentTrash


def test_trash_file(root):
    root.environment.service_user = "s-service"
    c = DeploymentTrash()
    c.prepare(root)
    assert "/etc/local/nixos/s-service-trash.nix" == c._trash_nix.path
