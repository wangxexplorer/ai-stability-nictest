"""Data validation and parsing utilities for NIC stability tests."""
import re
from typing import Dict, Any
from pathlib import Path

import yaml


_config_cache: Dict[str, Any] = {}


def parse_duration(duration_str: str) -> int:
    """Parse duration string to seconds.

    Supports formats: '7d', '168h', '30min', '10m', '60s', '60' (bare number).

    Args:
        duration_str: Duration string with optional unit suffix.

    Returns:
        Duration in seconds.

    Raises:
        ValueError: If the duration string cannot be parsed.
    """
    duration_str = duration_str.strip()

    match = re.match(r"^(\d+)\s*(d|h|min|m|s)?$", duration_str, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot parse duration: '{duration_str}'")

    value = int(match.group(1))
    unit = (match.group(2) or "s").lower()

    unit_to_seconds = {
        "d": 86400,
        "h": 3600,
        "min": 60,
        "m": 60,
        "s": 1,
    }

    return value * unit_to_seconds[unit]


def parse_speed(speed_str: str) -> int:
    """Parse NIC speed string to Mbps.

    Supports formats: '10000', '10Gb/s', '25G', '10000Mb/s', '25Gbps'.

    Args:
        speed_str: Speed string with optional unit suffix.

    Returns:
        Speed in Mbps.

    Raises:
        ValueError: If the speed string cannot be parsed.
    """
    speed_str = speed_str.lower().replace("mb/s", "").replace("mbps", "").strip()
    speed_str = speed_str.replace("gb/s", "").replace("gbps", "").strip()

    if "g" in speed_str:
        return int(float(speed_str.replace("g", "").strip()) * 1000)

    value = speed_str.strip()
    if not value:
        raise ValueError(f"Cannot parse speed: '{speed_str}'")
    return int(value)


def load_test_config() -> Dict[str, Any]:
    """Load test configuration from YAML file with caching.

    Resolves the config path relative to the project root directory.
    The configuration is loaded once and cached for subsequent calls.

    Returns:
        Parsed configuration dictionary.
    """
    global _config_cache
    if _config_cache:
        return _config_cache

    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config" / "test_config.yaml"

    with open(config_path, "r") as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache
