import pytest
import yaml
from pathlib import Path


@pytest.fixture(scope="session")
def test_config():
    config_path = Path(__file__).parent.parent / "config" / "test_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def device_config(test_config):
    return test_config.get("devices", {})


@pytest.fixture(scope="session")
def nic_config(test_config):
    return test_config.get("nics", [])


@pytest.fixture(scope="session")
def thresholds(test_config):
    return test_config.get("thresholds", {})
