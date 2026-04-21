import pytest
import yaml
from pathlib import Path


def pytest_configure(config):
    """Register custom pytest marks."""
    config.addinivalue_line("markers", "stress: mark test as stress test")
    config.addinivalue_line("markers", "kernel: mark test as kernel driver test")
    config.addinivalue_line("markers", "dpdk: mark test as DPDK driver test")
    config.addinivalue_line("markers", "rdma: mark test as RDMA driver test")
    config.addinivalue_line("markers", "longevity: mark test as longevity test")
    config.addinivalue_line("markers", "anomaly: mark test as anomaly test")
    config.addinivalue_line("markers", "mixed_data: mark test as mixed data test")
    config.addinivalue_line("markers", "business_flow: mark test as business flow test")


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
