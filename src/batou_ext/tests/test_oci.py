import batou
import pytest

from .. import oci


@pytest.fixture
def container(root):
    c = oci.Container(
        container_name="name",
        image="alpine",
    )

    c.prepare(root)
    return c


def patch_activate(mocker, activate):
    mocker.patch.object(activate, "_get_running_container_image_id")
    mocker.patch.object(activate, "_get_local_image_id")
    mocker.patch.object(activate, "_get_local_digest")
    mocker.patch.object(activate, "_docker_login")
    mocker.patch.object(activate, "_validate_remote_image")
    activate._validate_remote_image.return_value = False


@pytest.fixture
def activate(container, mocker, root):
    activate = container.activate()
    activate.prepare(root)
    patch_activate(mocker, activate)
    yield activate
    activate._remote_manifest_cache.clear()


def test_no_rebuild_flag_does_not_add_rebuild(root):
    c = oci.Container(
        container_name="name",
        image="alpine",
        rebuild=False,
    )
    c.prepare(root)
    with pytest.raises(AttributeError):
        c._activate_container

    # There are currently *no* component changes, as prepare only configures
    # the component, no verify has been called.
    assert not c.envfile.changed


def test_locally_updated_image_causes_restart(activate):
    activate._get_running_container_image_id.return_value = "v1"
    activate._get_local_image_id.return_value = "v2"

    with pytest.raises(batou.UpdateNeeded, match="Local version update."):
        activate.verify()
    assert activate._need_explicit_restart

    # There is no remote image validation in this case.
    activate._validate_remote_image.assert_not_called()


def test_remote_updated_image_causes_restart(activate):
    activate._get_running_container_image_id.return_value = "v1"
    activate._get_local_image_id.return_value = "v1"

    with pytest.raises(batou.UpdateNeeded, match="Remote version update."):
        activate.verify()
    assert activate._need_explicit_restart
    activate._validate_remote_image.assert_called()


def test_local_image_up_to_date_with_remote_causes_no_restart(activate):
    activate._get_running_container_image_id.return_value = "v1"
    activate._get_local_image_id.return_value = "v1"
    activate._validate_remote_image.return_value = True

    activate.verify()
    # Verify marks a restart *but* did not raise UpdatedNeede so update() is
    # never called!
    assert activate._need_explicit_restart

    # Remote image was validated:
    activate._validate_remote_image.assert_called()


def test_remote_image_validation_is_cached(root, activate, mocker):
    activate._get_running_container_image_id.return_value = "v1"
    activate._get_local_image_id.return_value = "v1"
    activate._validate_remote_image.return_value = False
    activate._get_local_digest.return_value = "local-digest"

    # Uncached call
    with pytest.raises(batou.UpdateNeeded, match="Remote version update."):
        activate.verify()

    # Validate is called with the local digest
    activate._validate_remote_image.assert_called_with(
        "alpine:latest@local-digest"
    )
    activate._validate_remote_image.reset_mock()

    # A *different* container will re-use the cache!
    c2 = oci.Container(container_name="second", image="alpine")
    c2.prepare(root)
    a2 = c2.activate()
    a2.prepare(root)

    patch_activate(mocker, a2)
    a2._get_running_container_image_id.return_value = "v1"
    a2._get_local_image_id.return_value = "v1"
    a2._validate_remote_image.return_value = False
    a2._get_local_digest.return_value = "local-digest"

    with pytest.raises(
        batou.UpdateNeeded, match="Cached remote version update."
    ):
        a2.verify()

    activate._validate_remote_image.assert_not_called()


def test_regsistry_address_triggers_login(container, activate):
    container.registry_address = "some-registry"
    activate._get_running_container_image_id.return_value = "v1"
    activate._get_local_image_id.return_value = "v1"
    with pytest.raises(batou.UpdateNeeded):
        activate.verify()
    activate._docker_login.assert_called_with()


def test_password_file_change_causes_restart(root):
    c = oci.Container(
        container_name="name",
        image="alpine",
        registry_address="mine",
        registry_user="ben",
        registry_password="utzer",
    )

    c.prepare(root)
    c.password_file.changed = True
    activate = c.activate()
    activate.prepare(root)

    with pytest.raises(batou.UpdateNeeded):
        activate.verify()

    assert activate._need_explicit_restart


def test_env_file_change_causes_restart(root):
    c = oci.Container(
        container_name="name",
        image="alpine",
    )

    c.prepare(root)
    c.envfile.changed = True
    activate = c.activate()
    activate.prepare(root)

    with pytest.raises(batou.UpdateNeeded):
        activate.verify()

    assert activate._need_explicit_restart
