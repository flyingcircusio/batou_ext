import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import configupdater
import pytest

from batou_ext import fcio


@pytest.fixture
def mock_environment():
    """Create a mock batou environment."""
    env = Mock()
    env.name = "testenv"
    env.overrides = {
        "provision": {
            "project": "testproject",
            "api_key": "testkey",
            "vm_environment": "testenv",
        }
    }
    env.hosts = {}
    env.exceptions = []
    env.service_user = "testuser"
    return env


@pytest.fixture
def sample_live_vms():
    """Sample live VM data from FCIO API."""
    return {
        "testhost01": {
            "name": "testhost01",
            "cores": 4,
            "disk": 50,
            "memory": 8192,  # 8 GiB in MiB
            "classes": ["role::generic", "role::web", "role::db"],
            "rbd_pool": "rbd.ssd",
            "service_description": "Test server",
            "aliases_srv": ["srv01", "srv02"],
            "aliases_fe": ["fe01"],
            "environment": "production",
        },
        "testhost02": {
            "name": "testhost02",
            "cores": 2,
            "disk": 30,
            "memory": 4096,  # 4 GiB in MiB
            "classes": ["role::generic", "role::web"],
            "rbd_pool": "rbd.hdd",
            "service_description": "",
            "aliases_srv": [],
            "aliases_fe": [],
            "environment": "production",
        },
    }


@pytest.fixture
def sample_config():
    """Sample environment.cfg content."""
    return """[host:testhost01]
data-cores = 2
data-disk = 30
data-ram = 4
data-roles =
    web
data-rbdpool = rbd.hdd
data-description = Old description
data-alias-srv = old-srv
data-alias-fe =

[host:testhost02]
data-cores = 2
data-disk = 30
data-ram = 4
data-roles =
    web
data-rbdpool = rbd.hdd

[component:provision]
project = testproject
api_key = testkey
vm_environment = staging
"""


class TestConvertAPIValue:
    """Tests for convert_api_value function."""

    def test_convert_memory(self):
        """Test memory conversion from MiB to GiB."""
        result = fcio.convert_api_value("memory", 8192)
        assert result == "8"

    def test_convert_memory_string(self):
        """Test memory conversion with string input."""
        result = fcio.convert_api_value("memory", "4096")
        assert result == "4"

    def test_convert_classes(self):
        """Test classes conversion to roles list."""
        result = fcio.convert_api_value(
            "classes", ["role::generic", "role::web", "role::db"]
        )
        assert result == ["db", "web"]

    def test_convert_classes_single(self):
        """Test classes conversion with single role."""
        result = fcio.convert_api_value(
            "classes", ["role::generic", "role::web"]
        )
        assert result == ["web"]

    def test_convert_aliases_srv(self):
        """Test aliases_srv conversion to sorted list."""
        result = fcio.convert_api_value("aliases_srv", ["srv01", "srv02"])
        assert result == ["srv01", "srv02"]

    def test_convert_aliases_fe(self):
        """Test aliases_fe conversion to sorted list."""
        result = fcio.convert_api_value("aliases_fe", ["fe01", "fe02"])
        assert result == ["fe01", "fe02"]

    def test_convert_aliases_empty_list(self):
        """Test aliases conversion with empty list."""
        result = fcio.convert_api_value("aliases_srv", [])
        assert result is None

    def test_convert_cores(self):
        """Test cores conversion."""
        result = fcio.convert_api_value("cores", 4)
        assert result == "4"

    def test_convert_disk(self):
        """Test disk conversion."""
        result = fcio.convert_api_value("disk", 50)
        assert result == "50"

    def test_convert_rbd_pool(self):
        """Test rbd_pool conversion."""
        result = fcio.convert_api_value("rbd_pool", "rbd.ssd")
        assert result == "rbd.ssd"

    def test_convert_service_description(self):
        """Test service_description conversion."""
        result = fcio.convert_api_value("service_description", "Test server")
        assert result == "Test server"

    def test_convert_service_description_none(self):
        """Test service_description conversion with None."""
        result = fcio.convert_api_value("service_description", None)
        assert result is None

    def test_convert_environment(self):
        """Test environment conversion (no transformation)."""
        result = fcio.convert_api_value("environment", "production")
        assert result == "production"

    def test_convert_unknown_key(self):
        """Test conversion with unknown key."""
        result = fcio.convert_api_value("unknown", "value")
        assert result == "value"


class TestFormatCfgValue:
    """Tests for format_cfg_value function."""

    def test_format_none(self):
        """Test formatting None value."""
        result = fcio.format_cfg_value(None)
        assert result == ""

    def test_format_list(self):
        """Test formatting list value."""
        result = fcio.format_cfg_value(["web", "db"])
        assert result == "web\n    db"

    def test_format_string(self):
        """Test formatting string value."""
        result = fcio.format_cfg_value("test value")
        assert result == "test value"

    def test_format_number(self):
        """Test formatting number value."""
        result = fcio.format_cfg_value(42)
        assert result == "42"


class TestParseCfgValue:
    """Tests for parse_cfg_value function."""

    def test_parse_none(self):
        """Test parsing None."""
        result = fcio.parse_cfg_value(None)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        option = Mock()
        option.value = ""
        result = fcio.parse_cfg_value(option)
        assert result is None

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string."""
        option = Mock()
        option.value = "   "
        result = fcio.parse_cfg_value(option)
        assert result is None

    def test_parse_multiline_list(self):
        """Test parsing multi-line list."""
        option = Mock()
        option.value = "web\n    db\n    cache"
        result = fcio.parse_cfg_value(option)
        assert result == ["web", "db", "cache"]

    def test_parse_multiline_list_with_blank_lines(self):
        """Test parsing multi-line list with blank lines."""
        option = Mock()
        option.value = "web\n    \n    db"
        result = fcio.parse_cfg_value(option)
        assert result == ["web", "db"]

    def test_parse_string(self):
        """Test parsing simple string."""
        option = Mock()
        option.value = "test value"
        result = fcio.parse_cfg_value(option)
        assert result == "test value"

    def test_parse_python_list(self):
        """Test parsing Python list literal."""
        option = Mock()
        option.value = "['web', 'db']"
        result = fcio.parse_cfg_value(option)
        assert result == ["web", "db"]

    def test_parse_python_number(self):
        """Test parsing Python number literal."""
        option = Mock()
        option.value = "42"
        result = fcio.parse_cfg_value(option)
        assert result == 42


class TestValuesEqual:
    """Tests for values_equal function."""

    def test_both_none(self):
        """Test comparison with both None."""
        assert fcio.values_equal(None, None) is True

    def test_one_none(self):
        """Test comparison with one None."""
        assert fcio.values_equal(None, "value") is False
        assert fcio.values_equal("value", None) is False

    def test_equal_strings(self):
        """Test comparison with equal strings."""
        assert fcio.values_equal("web", "web") is True

    def test_unequal_strings(self):
        """Test comparison with unequal strings."""
        assert fcio.values_equal("web", "db") is False

    def test_equal_lists(self):
        """Test comparison with equal lists."""
        assert fcio.values_equal(["web", "db"], ["web", "db"]) is True

    def test_equal_lists_unordered(self):
        """Test comparison with unordered lists."""
        assert fcio.values_equal(["web", "db"], ["db", "web"]) is True

    def test_unequal_lists(self):
        """Test comparison with unequal lists."""
        assert fcio.values_equal(["web", "db"], ["web", "cache"]) is False

    def test_multiline_string_vs_list(self):
        """Test comparison between multiline string and list."""
        assert fcio.values_equal("web\ndb", ["web", "db"]) is True

    def test_string_vs_single_item_list(self):
        """Test comparison between string and single-item list."""
        assert fcio.values_equal("web", ["web"]) is True

    def test_whitespace_insensitive(self):
        """Test that whitespace is ignored in comparison."""
        assert fcio.values_equal("  web  ", "web") is True


class TestGetConfigVMData:
    """Tests for get_config_vm_data function."""

    def test_extract_vm_data(self):
        """Test extracting VM data from config."""
        config = configupdater.ConfigUpdater()
        config.read_string(
            """
[host:vm01]
data-cores = 4
data-ram = 8
data-roles =
    web
    db

[host:vm02]
data-cores = 2
"""
        )
        result = fcio.get_config_vm_data(config)
        assert "vm01" in result
        assert "vm02" in result
        # parse_cfg_value evaluates Python literals, so "4" becomes 4
        assert result["vm01"]["data-cores"] == 4
        assert result["vm01"]["data-ram"] == 8
        assert result["vm01"]["data-roles"] == ["web", "db"]
        assert result["vm02"]["data-cores"] == 2

    def test_ignore_non_host_sections(self):
        """Test that non-host sections are ignored."""
        config = configupdater.ConfigUpdater()
        config.read_string(
            """
[component:provision]
project = test

[host:vm01]
data-cores = 4
"""
        )
        result = fcio.get_config_vm_data(config)
        assert "vm01" in result
        assert "component:provision" not in result
        assert len(result) == 1


class TestCompareVMData:
    """Tests for compare_vm_data function."""

    def test_no_differences(self):
        """Test comparison with no differences."""
        live_vm = {
            "cores": 4,
            "memory": 8192,
            "classes": ["role::web", "role::db"],
        }
        config_vm = {
            "data-cores": "4",
            "data-ram": "8",
            "data-roles": ["web", "db"],
        }
        result = fcio.compare_vm_data(live_vm, config_vm, mode="diff")
        assert len(result) == 0

    def test_differences_in_diff_mode(self):
        """Test comparison with differences in diff mode."""
        live_vm = {
            "cores": 4,
            "memory": 8192,
            "classes": ["role::web", "role::db"],
        }
        config_vm = {
            "data-cores": "2",
            "data-ram": "8",
            "data-roles": ["web"],
        }
        result = fcio.compare_vm_data(live_vm, config_vm, mode="diff")
        assert "data-cores" in result
        assert "data-roles" in result
        assert result["data-cores"] == ("2", "4")
        # convert_api_value converts ["role::web", "role::db"] to ["db", "web"]
        assert result["data-roles"] == (["web"], ["db", "web"])

    def test_all_fields_in_all_mode(self):
        """Test comparison in all mode includes all fields."""
        live_vm = {"cores": 4, "memory": 8192, "classes": ["role::web"]}
        config_vm = {
            "data-cores": "4",
            "data-ram": "8",
            "data-roles": ["web"],
        }
        result = fcio.compare_vm_data(live_vm, config_vm, mode="all")
        # All fields should be included even if they match
        assert "data-cores" in result
        assert "data-ram" in result
        assert "data-roles" in result

    def test_skip_empty_service_description(self):
        """Test that empty service_description is skipped."""
        live_vm = {"service_description": ""}
        config_vm = {}
        result = fcio.compare_vm_data(live_vm, config_vm, mode="diff")
        assert len(result) == 0

    def test_skip_none_values(self):
        """Test that None values are skipped."""
        live_vm = {"cores": None}
        config_vm = {}
        result = fcio.compare_vm_data(live_vm, config_vm, mode="diff")
        assert len(result) == 0


class TestProvisionUpdateFromLive:
    """Tests for Provision.update_from_live method."""

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_update_from_live_basic(
        self, mock_env_class, mock_create_client, sample_live_vms, sample_config
    ):
        """Test basic update from live data."""
        # Setup mocks
        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(sample_live_vms.values())
        mock_create_client.return_value = mock_api

        # Create temporary config file
        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            cfg_path.write_text(sample_config)

            # Create provision instance and run update
            provision = fcio.Provision(env_name="testenv", dry_run=False)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=False, env_path=env_dir
                    )

            # Read updated config
            config = configupdater.ConfigUpdater()
            config.read(cfg_path)

            # Verify updates were applied
            assert config["host:testhost01"]["data-cores"].value == "4"
            assert config["host:testhost01"]["data-disk"].value == "50"
            assert config["host:testhost01"]["data-ram"].value == "8"
            assert config["host:testhost01"]["data-rbdpool"].value == "rbd.ssd"
            assert (
                config["host:testhost01"]["data-description"].value
                == "Test server"
            )
            assert (
                config["host:testhost01"]["data-alias-srv"].value
                == "\nsrv01\nsrv02"
            )

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_update_from_live_dry_run(
        self, mock_env_class, mock_create_client, sample_live_vms, sample_config
    ):
        """Test dry run mode."""
        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(sample_live_vms.values())
        mock_create_client.return_value = mock_api

        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            original_content = sample_config
            cfg_path.write_text(original_content)

            provision = fcio.Provision(env_name="testenv", dry_run=True)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=False, env_path=env_dir
                    )

            # Verify config was not modified
            assert cfg_path.read_text() == original_content

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_update_vm_environment(
        self, mock_env_class, mock_create_client, sample_live_vms, sample_config
    ):
        """Test that vm_environment is updated."""
        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(sample_live_vms.values())
        mock_create_client.return_value = mock_api

        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            cfg_path.write_text(sample_config)

            provision = fcio.Provision(env_name="testenv", dry_run=False)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=False, env_path=env_dir
                    )

            config = configupdater.ConfigUpdater()
            config.read(cfg_path)

            # Verify vm_environment was updated
            assert (
                config["component:provision"]["vm_environment"].value
                == "production"
            )

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_update_verbose_output(
        self,
        mock_env_class,
        mock_create_client,
        sample_live_vms,
        sample_config,
        capsys,
    ):
        """Test verbose output mode."""
        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(sample_live_vms.values())
        mock_create_client.return_value = mock_api

        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            cfg_path.write_text(sample_config)

            provision = fcio.Provision(env_name="testenv", dry_run=False)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=True, env_path=env_dir
                    )

            captured = capsys.readouterr()
            # Check that verbose output includes section names
            assert "Updating [host:testhost01]" in captured.out
            assert "data-cores:" in captured.out

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_no_updates_needed(
        self, mock_env_class, mock_create_client, sample_config, capsys
    ):
        """Test when no updates are needed."""
        # Create live data that matches config
        live_vms = {
            "testhost01": {
                "name": "testhost01",
                "cores": 2,
                "disk": 30,
                "memory": 4096,
                "classes": ["role::generic", "role::web"],
                "rbd_pool": "rbd.hdd",
                "service_description": "",
                "aliases_srv": [],
                "aliases_fe": [],
                "environment": "staging",
            }
        }

        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(live_vms.values())
        mock_create_client.return_value = mock_api

        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            cfg_path.write_text(sample_config)

            provision = fcio.Provision(env_name="testenv", dry_run=False)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=False, env_path=env_dir
                    )

            captured = capsys.readouterr()
            assert "No updates needed" in captured.out

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_handles_vms_only_in_live_data(
        self, mock_env_class, mock_create_client, sample_config, capsys
    ):
        """Test handling of VMs that exist only in live data."""
        live_vms = {
            "testhost01": {
                "name": "testhost01",
                "cores": 2,
                "memory": 4096,
                "classes": ["role::web"],
                "environment": "production",
            },
            "newhost": {
                "name": "newhost",
                "cores": 4,
                "memory": 8192,
                "classes": ["role::db"],
                "environment": "production",
            },
        }

        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(live_vms.values())
        mock_create_client.return_value = mock_api

        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            cfg_path.write_text(sample_config)

            provision = fcio.Provision(env_name="testenv", dry_run=False)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=False, env_path=env_dir
                    )

            captured = capsys.readouterr()
            assert "VMs in live data but not in config" in captured.err
            assert "newhost" in captured.err

    @patch("batou_ext.fcio.create_xmlrpc_client")
    @patch("batou.environment.Environment")
    def test_handles_vms_only_in_config(
        self, mock_env_class, mock_create_client, sample_config, capsys
    ):
        """Test handling of VMs that exist only in config."""
        live_vms = {
            "testhost01": {
                "name": "testhost01",
                "cores": 2,
                "memory": 4096,
                "classes": ["role::web"],
                "environment": "production",
            }
        }

        mock_env = Mock()
        mock_env.name = "testenv"
        mock_env.load = Mock()
        mock_env.load_secrets = Mock()
        mock_env.exceptions = []
        mock_env.overrides = {
            "provision": {"project": "testproject", "api_key": "testkey"}
        }
        mock_env_class.return_value = mock_env

        mock_api = Mock()
        mock_api.query.return_value = list(live_vms.values())
        mock_create_client.return_value = mock_api

        with tempfile.TemporaryDirectory() as tmpdir:
            env_dir = Path(tmpdir) / "environments" / "testenv"
            env_dir.mkdir(parents=True)
            cfg_path = env_dir / "environment.cfg"
            cfg_path.write_text(sample_config)

            provision = fcio.Provision(env_name="testenv", dry_run=False)
            with patch.object(provision, "load_env", return_value=mock_env):
                with patch.object(provision, "get_api", return_value=mock_api):
                    provision.update_from_live(
                        mode="diff", verbose=False, env_path=env_dir
                    )

            captured = capsys.readouterr()
            assert "Hosts in config but not in live data" in captured.err
            assert "testhost02" in captured.err
