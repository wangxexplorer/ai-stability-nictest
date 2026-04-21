# NIC稳定性测试系统 - 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的NIC稳定性测试系统，包括50个用例的自动化测试、pytest规范、Prometheus监控集成、Excel用例清单生成

**架构:** 基于pytest的测试框架，支持多驱动类型（kernel/dpdk/rdma），双设备互测拓扑，Prometheus+node_exporter监控

**Tech Stack:** Python 3.9+, pytest, paramiko, prometheus-client, pandas/openpyxl, PyYAML, Jinja2

---

## 前置条件

- [ ] **确认用例清单已review通过**（.sisyphus/drafts/testcase-list-review.md）
- [ ] **确认测试拓扑设备可用**（DUT+Tester+Monitor）
- [ ] **确认驱动类型**（kernel/dpdk/rdma已部署）

---

## Chunk 1: 项目初始化与目录结构

### Task 1.1: 创建项目目录结构

**Files:**
- Create: `config/test_config.yaml`
- Create: `config/prometheus_config.yaml`
- Create: `testcase/__init__.py`
- Create: `core/__init__.py`
- Create: `utils/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `scripts/setup_env.sh`
- Create: `.sisyphus/plans/`

- [ ] **Step 1: 创建完整目录结构**

```bash
# 创建项目根目录结构
mkdir -p config testcase core utils tests scripts result/{raw,reports,logs,archives}

# 创建__init__.py文件
touch testcase/__init__.py core/__init__.py utils/__init__.py tests/__init__.py
```

- [ ] **Step 2: 创建基本配置文件**

**config/test_config.yaml**
```yaml
# 测试拓扑配置
topology:
  device_role: "dut"  # 或 "tester"
  connection_mode: "direct"  # 或 "switch"
  
# 网卡配置
nics:
  - name: "eth0"
    pci: "0000:01:00.0"
    driver: "kernel"  # kernel/dpdk/rdma
    speed: "25G"
    tester_port: "eth0"
    
  - name: "eth1"
    pci: "0000:01:00.1"
    driver: "dpdk"
    speed: "100G"
    tester_port: "eth1"

# 设备连接信息
devices:
  dut:
    ip: "192.168.1.10"
    user: "root"
    password: "password"
    ssh_port: 22
  tester:
    ip: "192.168.1.11"
    user: "root"
    password: "password"
    ssh_port: 22
  monitor:
    ip: "192.168.1.12"
    prometheus_url: "http://192.168.1.12:9090"

# 全局测试参数
test_parameters:
  sample_interval: "10s"
  default_duration: "4h"
  default_bandwidth_target: "80%"

# 验证阈值（可自定义）
thresholds:
  packet_loss_rate: "0.1%"
  latency_jitter: "20%"
  bandwidth_achievement: "95%"
  cpu_usage_max: "80%"
  memory_growth_max: "10%"
  nic_errors_max: 0
```

- [ ] **Step 3: 初始化pytest配置**

**tests/conftest.py**
```python
"""Pytest fixtures and configuration."""
import pytest
import yaml
from pathlib import Path


@pytest.fixture(scope="session")
def test_config():
    """Load test configuration."""
    config_path = Path(__file__).parent.parent / "config" / "test_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def device_config(test_config):
    """Get device configuration."""
    return test_config.get("devices", {})


@pytest.fixture(scope="session")
def nic_config(test_config):
    """Get NIC configuration."""
    return test_config.get("nics", [])


@pytest.fixture(scope="session")
def thresholds(test_config):
    """Get validation thresholds."""
    return test_config.get("thresholds", {})
```

- [ ] **Step 4: 创建requirements.txt**

**requirements.txt**
```
pytest>=7.0.0
pytest-html>=3.2.0
pytest-xdist>=2.5.0
pyyaml>=6.0
jinja2>=3.0
requests>=2.28.0
paramiko>=2.11.0
pandas>=1.5.0
openpyxl>=3.0.0
prometheus-client>=0.14.0
psutil>=5.9.0
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: initialize project structure and basic configuration"
```

---

## Chunk 2: 公共工具模块实现

### Task 2.1: 实现SSH客户端工具

**Files:**
- Create: `utils/ssh_client.py`
- Test: `tests/test_ssh_client.py`

- [ ] **Step 1: 创建SSHClient类**

**utils/ssh_client.py**
```python
"""SSH client for remote device management."""
import paramiko
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SSHClient:
    """SSH client for executing commands on remote devices."""
    
    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self._client: Optional[paramiko.SSHClient] = None
    
    def connect(self, timeout: int = 30) -> None:
        """Establish SSH connection."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            username=self.username,
            password=self.password,
            port=self.port,
            timeout=timeout
        )
        logger.info(f"Connected to {self.host}:{self.port}")
    
    def execute(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """Execute command and return (exit_code, stdout, stderr)."""
        if not self._client:
            raise RuntimeError("SSH client not connected")
        
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        stdout_str = stdout.read().decode('utf-8')
        stderr_str = stderr.read().decode('utf-8')
        
        return exit_code, stdout_str, stderr_str
    
    def close(self) -> None:
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info(f"Disconnected from {self.host}")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

- [ ] **Step 2: 编写SSHClient测试**

**tests/test_ssh_client.py**
```python
"""Tests for SSH client."""
import pytest
from unittest.mock import Mock, patch
from utils.ssh_client import SSHClient


def test_ssh_client_initialization():
    """Test SSH client initialization."""
    client = SSHClient("192.168.1.1", "root", "password")
    assert client.host == "192.168.1.1"
    assert client.username == "root"
    assert client.password == "password"
    assert client.port == 22


def test_ssh_client_execute_without_connection():
    """Test that execute raises error if not connected."""
    client = SSHClient("192.168.1.1", "root", "password")
    with pytest.raises(RuntimeError, match="SSH client not connected"):
        client.execute("ls")
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_ssh_client.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 4: Commit**

```bash
git add utils/ssh_client.py tests/test_ssh_client.py
git commit -m "feat: add SSH client utility with paramiko"
```

---

### Task 2.2: 实现Prometheus监控客户端

**Files:**
- Create: `utils/prometheus_client.py`
- Test: `tests/test_prometheus_client.py`

- [ ] **Step 1: 创建PrometheusClient类**

**utils/prometheus_client.py**
```python
"""Prometheus client for monitoring metrics."""
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for querying Prometheus metrics."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/v1"
    
    def query(self, query: str, time: Optional[datetime] = None) -> Dict:
        """Execute instant query."""
        params = {'query': query}
        if time:
            params['time'] = time.timestamp()
        
        response = requests.get(f"{self.api_url}/query", params=params)
        response.raise_for_status()
        return response.json()
    
    def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "10s"
    ) -> Dict:
        """Execute range query."""
        params = {
            'query': query,
            'start': start.timestamp(),
            'end': end.timestamp(),
            'step': step
        }
        
        response = requests.get(f"{self.api_url}/query_range", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_cpu_usage(self, instance: str, duration: str = "5m") -> float:
        """Get CPU usage percentage."""
        query = f'100 - (avg(irate(node_cpu_seconds_total{{mode="idle",instance="{instance}"}}[{duration}])) * 100)'
        result = self.query(query)
        
        if result['data']['result']:
            return float(result['data']['result'][0]['value'][1])
        return 0.0
    
    def get_memory_usage(self, instance: str) -> float:
        """Get memory usage percentage."""
        query = f'100 * (1 - node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}})'
        result = self.query(query)
        
        if result['data']['result']:
            return float(result['data']['result'][0]['value'][1])
        return 0.0
    
    def get_nic_metrics(self, instance: str, nic: str) -> Dict:
        """Get NIC metrics (rx/tx bytes, errors, dropped)."""
        metrics = {}
        
        # RX/TX bytes
        queries = {
            'rx_bytes': f'node_network_receive_bytes_total{{device="{nic}",instance="{instance}"}}',
            'tx_bytes': f'node_network_transmit_bytes_total{{device="{nic}",instance="{instance}"}}',
            'rx_errors': f'node_network_receive_errs_total{{device="{nic}",instance="{instance}"}}',
            'tx_errors': f'node_network_transmit_errs_total{{device="{nic}",instance="{instance}"}}',
            'rx_dropped': f'node_network_receive_drop_total{{device="{nic}",instance="{instance}"}}',
            'tx_dropped': f'node_network_transmit_drop_total{{device="{nic}",instance="{instance}"}}'
        }
        
        for metric_name, query in queries.items():
            result = self.query(query)
            if result['data']['result']:
                metrics[metric_name] = float(result['data']['result'][0]['value'][1])
            else:
                metrics[metric_name] = 0.0
        
        return metrics
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_prometheus_client.py -v
```

- [ ] **Step 3: Commit**

```bash
git add utils/prometheus_client.py tests/test_prometheus_client.py
git commit -m "feat: add Prometheus monitoring client"
```

---

### Task 2.3: 实现NIC工具类

**Files:**
- Create: `utils/nic_helper.py`
- Test: `tests/test_nic_helper.py`

- [ ] **Step 1: 创建NICHelper类**

**utils/nic_helper.py**
```python
"""NIC helper utilities for network interface operations."""
import re
from typing import Dict, List, Optional, Tuple
from utils.ssh_client import SSHClient


class NICHelper:
    """Helper class for NIC operations."""
    
    @staticmethod
    def get_nic_info(ssh_client: SSHClient, nic_name: str) -> Dict:
        """Get NIC information."""
        exit_code, stdout, stderr = ssh_client.execute(f"ethtool {nic_name}")
        
        info = {'name': nic_name}
        
        if exit_code == 0:
            # Parse ethtool output
            for line in stdout.split('\n'):
                if 'Speed:' in line:
                    info['speed'] = line.split(':')[1].strip()
                elif 'Duplex:' in line:
                    info['duplex'] = line.split(':')[1].strip()
                elif 'Link detected:' in line:
                    info['link_up'] = 'yes' in line.lower()
        
        return info
    
    @staticmethod
    def get_nic_statistics(ssh_client: SSHClient, nic_name: str) -> Dict:
        """Get NIC error statistics."""
        stats = {}
        
        # Read from /sys/class/net/
        stat_files = [
            'rx_errors', 'tx_errors',
            'rx_dropped', 'tx_dropped',
            'rx_frame_errors', 'rx_crc_errors'
        ]
        
        for stat_file in stat_files:
            cmd = f"cat /sys/class/net/{nic_name}/statistics/{stat_file}"
            exit_code, stdout, stderr = ssh_client.execute(cmd)
            
            if exit_code == 0:
                try:
                    stats[stat_file] = int(stdout.strip())
                except ValueError:
                    stats[stat_file] = 0
            else:
                stats[stat_file] = 0
        
        return stats
    
    @staticmethod
    def set_nic_queues(ssh_client: SSHClient, nic_name: str, queues: int) -> bool:
        """Set NIC combined queues using ethtool."""
        cmd = f"ethtool -L {nic_name} combined {queues}"
        exit_code, stdout, stderr = ssh_client.execute(cmd)
        
        return exit_code == 0
    
    @staticmethod
    def set_ring_size(ssh_client: SSHClient, nic_name: str, rx_size: int, tx_size: int) -> bool:
        """Set NIC ring size using ethtool."""
        cmd = f"ethtool -G {nic_name} rx {rx_size} tx {tx_size}"
        exit_code, stdout, stderr = ssh_client.execute(cmd)
        
        return exit_code == 0
    
    @staticmethod
    def get_queue_config(ssh_client: SSHClient, nic_name: str) -> Dict:
        """Get current queue configuration."""
        config = {}
        
        # Get queue count
        exit_code, stdout, stderr = ssh_client.execute(f"ethtool -l {nic_name}")
        if exit_code == 0:
            for line in stdout.split('\n'):
                if 'Combined:' in line:
                    try:
                        config['combined'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
        
        # Get ring size
        exit_code, stdout, stderr = ssh_client.execute(f"ethtool -g {nic_name}")
        if exit_code == 0:
            for line in stdout.split('\n'):
                if 'RX:' in line and 'Current' not in line:
                    try:
                        config['rx_ring'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif 'TX:' in line and 'Current' not in line:
                    try:
                        config['tx_ring'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
        
        return config
```

- [ ] **Step 2: Commit**

```bash
git add utils/nic_helper.py tests/test_nic_helper.py
git commit -m "feat: add NIC helper utilities"
```

---

## Chunk 3: 核心测试框架实现

### Task 3.1: 实现测试基类

**Files:**
- Create: `testcase/base.py`
- Create: `core/runner.py`
- Create: `core/monitor.py`
- Create: `core/reporter.py`

- [ ] **Step 1: 创建BaseTestCase基类**

**testcase/base.py**
```python
"""Base test case for NIC stability tests."""
import pytest
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseTestCase(ABC):
    """Base class for all NIC stability test cases."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.test_id = config.get('test_id', 'unknown')
        self.test_name = config.get('test_name', 'Unknown Test')
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.results: Dict[str, Any] = {}
        
    @abstractmethod
    def setup(self) -> None:
        """Setup test environment."""
        pass
    
    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """Execute test and return results."""
        pass
    
    @abstractmethod
    def teardown(self) -> None:
        """Cleanup test environment."""
        pass
    
    @abstractmethod
    def validate(self, results: Dict[str, Any]) -> bool:
        """Validate test results against thresholds."""
        pass
    
    def execute(self) -> Dict[str, Any]:
        """Execute complete test lifecycle."""
        try:
            logger.info(f"Starting test: {self.test_name}")
            self.start_time = datetime.now()
            
            # Setup
            self.setup()
            
            # Run test
            self.results = self.run()
            
            # Validate
            passed = self.validate(self.results)
            self.results['passed'] = passed
            
            return self.results
            
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
            self.results['passed'] = False
            self.results['error'] = str(e)
            return self.results
            
        finally:
            self.end_time = datetime.now()
            self.teardown()
            logger.info(f"Test completed: {self.test_name}")
```

- [ ] **Step 2: 创建TestRunner类**

**core/runner.py**
```python
"""Test runner for executing test cases."""
import logging
from typing import List, Dict, Any
from testcase.base import BaseTestCase

logger = logging.getLogger(__name__)


class TestRunner:
    """Runner for executing test cases."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    def run_test(self, test_case: BaseTestCase) -> Dict[str, Any]:
        """Run a single test case."""
        logger.info(f"Running test: {test_case.test_name}")
        result = test_case.execute()
        self.results.append(result)
        return result
    
    def run_tests(self, test_cases: List[BaseTestCase]) -> List[Dict[str, Any]]:
        """Run multiple test cases."""
        for test_case in test_cases:
            self.run_test(test_case)
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test execution summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get('passed', False))
        failed = total - passed
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / total if total > 0 else 0.0
        }
```

- [ ] **Step 3: Commit**

```bash
git add testcase/base.py core/runner.py core/monitor.py core/reporter.py
git commit -m "feat: add base test framework classes"
```

---

## Chunk 4: Excel用例清单生成

### Task 4.1: 生成Excel用例清单

**Files:**
- Create: `scripts/generate_testcase_excel.py`
- Create: `testcase_list.xlsx` (output)

- [ ] **Step 1: 创建Excel生成脚本**

**scripts/generate_testcase_excel.py**
```python
#!/usr/bin/env python3
"""Generate testcase_list.xlsx from review document."""
import pandas as pd
from pathlib import Path


def generate_stress_test_cases():
    """Generate stress test cases."""
    cases = []
    
    # Kernel TCP Stress Tests
    kernel_tcp_cases = [
        ("ST-001", "Kernel快速基准验证-80%带宽", "kernel", "30min", "80%", "1500B", "TCP", 1, "iperf3", "P1", "必选"),
        ("ST-002", "Kernel标准压力测试-80%带宽-16流", "kernel", "1h", "80%", "1500B", "TCP", 16, "iperf3", "P1", "必选"),
        ("ST-003", "Kernel高压压力测试-90%带宽", "kernel", "4h", "90%", "1500B", "TCP", 16, "iperf3", "P1", "必选"),
        ("ST-004", "Kernel小包PPS极限测试-64B", "kernel", "4h", "80%", "64B", "TCP", 32, "iperf3", "P1", "必选"),
        ("ST-005", "Kernel大包带宽测试-64KB", "kernel", "4h", "80%", "64KB", "TCP", 8, "iperf3", "P1", "必选"),
        ("ST-006", "Kernel Jumbo Frame测试-9000B", "kernel", "1h", "80%", "9000B", "TCP", 8, "iperf3", "P1", "必选"),
        ("ST-007", "Kernel极高带宽测试-95%", "kernel", "1h", "95%", "1500B", "TCP", 16, "iperf3", "P1", "必选"),
        ("ST-008", "Kernel长压力测试-24h", "kernel", "24h", "80%", "1500B", "TCP", 8, "iperf3", "P1", "必选"),
    ]
    
    # Kernel UDP Stress Tests
    kernel_udp_cases = [
        ("ST-009", "Kernel UDP带宽测试-80%", "kernel", "1h", "80%", "1500B", "UDP", 16, "iperf3 -u", "P1", "必选"),
        ("ST-010", "Kernel UDP丢包测试-小包", "kernel", "4h", "80%", "64B", "UDP", 32, "iperf3 -u", "P1", "必选"),
        ("ST-011", "Kernel UDP PPS极限测试-64B高频", "kernel", "4h", "90%", "64B", "UDP", 64, "iperf3 -u", "P1", "必选"),
    ]
    
    # DPDK Stress Tests
    dpdk_cases = [
        ("ST-012", "DPDK标准压力测试", "dpdk", "4h", "80%", "1500B", "-", 16, "pktgen", "P1", "必选"),
        ("ST-013", "DPDK小包PPS测试", "dpdk", "4h", "80%", "64B", "-", 32, "pktgen", "P1", "必选"),
        ("ST-014", "DPDK高压测试-90%", "dpdk", "1h", "90%", "1500B", "-", 16, "pktgen", "P1", "必选"),
    ]
    
    # RDMA Stress Tests (Updated with 256 QP, bidirectional)
    rdma_cases = [
        ("ST-015", "RDMA Write双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_write_bw -b", 256, "perftest", "P1", "必选"),
        ("ST-016", "RDMA Read双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_read_bw -b", 256, "perftest", "P1", "必选"),
        ("ST-017", "RDMA Send双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_send_bw -b", 256, "perftest", "P1", "必选"),
        ("ST-018", "RDMA Write延迟测试-256QP", "rdma", "30min", "-", "-", "ib_write_lat", 256, "perftest", "P1", "必选"),
    ]
    
    cases.extend(kernel_tcp_cases)
    cases.extend(kernel_udp_cases)
    cases.extend(dpdk_cases)
    cases.extend(rdma_cases)
    
    return cases


def generate_longevity_test_cases():
    """Generate longevity test cases."""
    cases = [
        ("LT-001", "Kernel快速长时测试-24h", "kernel", "24h", "75%", "1500B", "TCP", 8, "恒定", "iperf3", "P1", "必选"),
        ("LT-002", "Kernel标准长时测试-7x24h", "kernel", "168h", "75%", "1500B", "TCP", 8, "恒定", "iperf3", "P1", "必选"),
        ("LT-003", "Kernel深度长时测试-15天", "kernel", "360h", "75%", "1500B", "TCP", 8, "恒定", "iperf3", "P2", "必选"),
        ("LT-004", "DPDK标准长时测试-7x24h", "dpdk", "168h", "75%", "1500B", "-", 8, "恒定", "pktgen", "P1", "必选"),
        ("LT-005", "RDMA标准长时测试-7x24h", "rdma", "168h", "75%", "-", "ib_write_bw", 1, "恒定", "perftest", "P1", "必选"),
        ("LT-006", "Kernel周期波动流量测试", "kernel", "168h", "50%~90%波动", "1500B", "TCP", 8, "周期波动", "iperf3", "P2", "可选"),
    ]
    return cases


def generate_anomaly_test_cases():
    """Generate anomaly test cases."""
    cases = [
        # Kernel Anomaly Tests (11 cases including new queue config test)
        ("AN-001", "Kernel链路中断测试", "kernel", "链路中断", "ifconfig eth0 down/up", "链路UP+流量恢复30s", "P0", "必选"),
        ("AN-002", "Kernel驱动重启测试", "kernel", "驱动重启", "modprobe -r/r driver", "驱动可用+流量恢复30s", "P0", "必选"),
        ("AN-003", "Kernel流量突发测试", "kernel", "流量突发", "瞬时90%带宽高压", "流量稳定", "P1", "必选"),
        ("AN-004", "Kernel SYN Flood攻击", "kernel", "DDoS攻击", "hping3 -S flood", "攻击结束流量恢复", "P1", "必选"),
        ("AN-005", "Kernel UDP Flood攻击", "kernel", "DDoS攻击", "hping3 -2 flood", "攻击结束流量恢复", "P1", "必选"),
        ("AN-006", "Kernel畸形包测试-超大包", "kernel", "畸形包", "tcpreplay oversized packet", "error记录", "P1", "必选"),
        ("AN-007", "Kernel畸形包测试-超小包", "kernel", "畸形包", "tcpreplay undersize packet", "error记录", "P1", "必选"),
        ("AN-008", "Kernel小包PPS攻击", "kernel", "小包攻击", "iperf3 -u -l 64 -P 64", "流量恢复", "P1", "必选"),
        ("AN-014", "Kernel队列数和队列深度组合测试", "kernel", "队列配置变更", "ethtool修改队列数/深度组合", "流量稳定+error计数", "P1", "必选"),
        
        # DPDK Anomaly Tests
        ("AN-010", "DPDK链路中断测试", "dpdk", "链路中断", "ifconfig down/up", "DPDK重初始化+流量恢复", "P0", "必选"),
        ("AN-011", "DPDK驱动重启测试", "dpdk", "驱动重启", "DPDK rebind/reinit", "DPDK可用+流量恢复", "P0", "必选"),
        ("AN-012", "DPDK SYN Flood攻击", "dpdk", "DDoS攻击", "hping3 -S flood", "应用层恢复", "P1", "必选"),
        ("AN-013", "DPDK小包PPS攻击", "dpdk", "小包攻击", "pktgen high PPS", "流量恢复", "P1", "必选"),
        
        # RDMA Anomaly Tests (Optional)
        ("AN-015", "RDMA异常恢复测试", "rdma", "RDMA异常", "QP状态异常恢复", "QP状态恢复", "P2", "可选"),
    ]
    return cases


def generate_mixed_data_test_cases():
    """Generate mixed data test cases."""
    cases = [
        ("MX-001", "Kernel包大小混合测试", "kernel", "包大小混合", "64B(20%)+512B(30%)+1500B(40%)+64KB(10%)", "4h", "iperf3多流", "P1", "必选"),
        ("MX-002", "Kernel协议混合测试", "kernel", "协议混合", "TCP(60%)+UDP(40%)", "4h", "iperf3 TCP+UDP", "P1", "必选"),
        ("MX-003", "Kernel全混合测试", "kernel", "包大小+协议混合", "包大小混合+协议混合", "4h", "iperf3多流", "P1", "必选"),
        ("MX-004", "DPDK包大小混合测试", "dpdk", "包大小混合", "64B(20%)+512B(30%)+1500B(40%)+64KB(10%)", "4h", "pktgen", "P1", "必选"),
        ("MX-005", "DPDK协议混合测试", "dpdk", "协议混合", "TCP(60%)+UDP(40%)模拟", "4h", "pktgen", "P1", "必选"),
        ("MX-006", "DPDK全混合测试", "dpdk", "包大小+协议混合", "包大小混合+协议混合", "4h", "pktgen", "P1", "必选"),
    ]
    return cases


def generate_business_flow_test_cases():
    """Generate business flow test cases."""
    cases = [
        ("BF-001", "Web服务业务流测试", "kernel", "Web服务", "nginx", "ab/curl", "4h", "P1", "必选"),
        ("BF-002", "数据库业务流测试", "kernel", "数据库", "MySQL", "sysbench", "4h", "P1", "必选"),
        ("BF-003", "存储业务流测试", "kernel", "存储", "NFS Server", "fio", "4h", "P1", "必选"),
        ("BF-004", "视频流业务流测试", "kernel", "视频流", "nginx-rtmp", "ffmpeg", "4h", "P2", "可选"),
        ("BF-005", "消息队列业务流测试", "kernel", "消息队列", "Kafka", "producer/consumer", "4h", "P2", "可选"),
        ("BF-006", "微服务RPC业务流测试", "kernel", "微服务", "gRPC Server", "ghz", "4h", "P2", "可选"),
    ]
    return cases


def main():
    """Generate testcase_list.xlsx."""
    # Create DataFrames for each test type
    
    # Stress Tests
    stress_cases = generate_stress_test_cases()
    df_stress = pd.DataFrame(
        stress_cases,
        columns=["用例ID", "用例名称", "驱动类型", "时长", "带宽目标", "包大小", 
                "协议", "并发流", "流量工具", "优先级", "必选/可选"]
    )
    df_stress["用例类型"] = "stress"
    df_stress["对应Python文件"] = "testcase/stress_test.py"
    
    # Longevity Tests
    longevity_cases = generate_longevity_test_cases()
    df_longevity = pd.DataFrame(
        longevity_cases,
        columns=["用例ID", "用例名称", "驱动类型", "时长", "带宽目标", "包大小",
                "协议", "并发流", "流量模式", "流量工具", "优先级", "必选/可选"]
    )
    df_longevity["用例类型"] = "longevity"
    df_longevity["对应Python文件"] = "testcase/longevity_test.py"
    
    # Anomaly Tests
    anomaly_cases = generate_anomaly_test_cases()
    df_anomaly = pd.DataFrame(
        anomaly_cases,
        columns=["用例ID", "用例名称", "驱动类型", "异常类型", "异常操作", "恢复验证", "优先级", "必选/可选"]
    )
    df_anomaly["用例类型"] = "anomaly"
    df_anomaly["对应Python文件"] = "testcase/anomaly_test.py"
    
    # Mixed Data Tests
    mixed_cases = generate_mixed_data_test_cases()
    df_mixed = pd.DataFrame(
        mixed_cases,
        columns=["用例ID", "用例名称", "驱动类型", "混合类型", "混合比例", "时长", "流量工具", "优先级", "必选/可选"]
    )
    df_mixed["用例类型"] = "mixed_data"
    df_mixed["对应Python文件"] = "testcase/mixed_data_test.py"
    
    # Business Flow Tests
    business_cases = generate_business_flow_test_cases()
    df_business = pd.DataFrame(
        business_cases,
        columns=["用例ID", "用例名称", "驱动类型", "业务场景", "服务端工具", "客户端工具", "时长", "优先级", "必选/可选"]
    )
    df_business["用例类型"] = "business_flow"
    df_business["对应Python文件"] = "testcase/business_flow_test.py"
    
    # Combine all test cases
    all_cases = pd.concat([df_stress, df_longevity, df_anomaly, df_mixed, df_business], ignore_index=True)
    
    # Add common columns
    all_cases["状态"] = "active"
    all_cases["负责人"] = ""
    all_cases["最后更新时间"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    # Reorder columns
    column_order = [
        "用例ID", "用例名称", "用例类型", "驱动类型", "优先级", "必选/可选",
        "对应Python文件", "状态", "负责人", "最后更新时间"
    ]
    all_cases = all_cases[column_order + [c for c in all_cases.columns if c not in column_order]]
    
    # Save to Excel
    output_path = Path(__file__).parent.parent / "testcase_list.xlsx"
    all_cases.to_excel(output_path, index=False, sheet_name="TestCases")
    
    print(f"Generated testcase_list.xlsx with {len(all_cases)} test cases")
    print(f"Location: {output_path}")
    
    # Print summary
    summary = all_cases.groupby("用例类型").size()
    print("\nTest case summary:")
    for test_type, count in summary.items():
        print(f"  {test_type}: {count} cases")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行Excel生成脚本**

```bash
python scripts/generate_testcase_excel.py
```

Expected output:
```
Generated testcase_list.xlsx with 50 test cases
Location: /root/wangxiao_ai/ai-stability-nictest/testcase_list.xlsx

Test case summary:
  stress: 18 cases
  longevity: 6 cases
  anomaly: 14 cases
  mixed_data: 6 cases
  business_flow: 6 cases
```

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_testcase_excel.py testcase_list.xlsx
git commit -m "feat: generate testcase_list.xlsx with 50 test cases"
```

---

## Chunk 5: Pytest规范文档

### Task 5.1: 生成pytest规范文档

**Files:**
- Create: `docs/pytest-guidelines.md`

- [ ] **Step 1: 创建pytest规范文档**

**docs/pytest-guidelines.md**
```markdown
# NIC稳定性测试 - Pytest规范文档

## 1. 测试文件组织

### 1.1 目录结构
```
tests/
├── conftest.py              # pytest fixtures和配置
├── test_ssh_client.py       # SSH客户端测试
├── test_prometheus_client.py # Prometheus客户端测试
├── test_nic_helper.py       # NIC工具测试
├── test_stress_kernel.py    # Kernel压力测试
├── test_stress_dpdk.py      # DPDK压力测试
├── test_stress_rdma.py      # RDMA压力测试
├── test_longevity_kernel.py # Kernel长时间测试
├── test_longevity_dpdk.py   # DPDK长时间测试
├── test_anomaly_kernel.py   # Kernel异常测试
├── test_mixed_data.py       # 混合数据测试
└── test_business_flow.py    # 业务流测试
```

### 1.2 文件命名规范
- 测试文件以 `test_` 开头
- 测试函数以 `test_` 开头
- 测试类以 `Test` 开头（如需要）

## 2. 测试函数命名规范

### 2.1 命名格式
```python
# 压力测试命名
def test_stress_kernel_tcp_80percent_1500b_16stream_4h():
    """Test kernel TCP stress with 80% bandwidth, 1500B packet, 16 streams, 4 hours."""
    pass

# 长时间测试命名
def test_longevity_kernel_7x24h_75percent():
    """Test kernel longevity for 7x24 hours at 75% bandwidth."""
    pass

# 异常测试命名
def test_anomaly_kernel_link_interrupt_recovery():
    """Test kernel link interrupt recovery."""
    pass
```

### 2.2 命名要素
- 测试类型（stress/longevity/anomaly/mixed/business）
- 驱动类型（kernel/dpdk/rdma）
- 关键参数（带宽/包大小/并发流/时长）
- 测试目的

## 3. 测试标记（Markers）使用

### 3.1 测试类型标记
```python
import pytest

@pytest.mark.stress
def test_stress_kernel_tcp():
    pass

@pytest.mark.longevity
def test_longevity_kernel():
    pass

@pytest.mark.anomaly
def test_anomaly_kernel_link():
    pass

@pytest.mark.mixed_data
def test_mixed_data_kernel():
    pass

@pytest.mark.business_flow
def test_business_web_service():
    pass
```

### 3.2 驱动类型标记
```python
@pytest.mark.kernel
def test_kernel_stress():
    pass

@pytest.mark.dpdk
def test_dpdk_stress():
    pass

@pytest.mark.rdma
def test_rdma_stress():
    pass
```

### 3.3 优先级标记
```python
@pytest.mark.p0  # 核心必选
def test_critical_feature():
    pass

@pytest.mark.p1  # 重要必选
def test_important_feature():
    pass

@pytest.mark.p2  # 可选
def test_optional_feature():
    pass
```

## 4. Fixtures使用规范

### 4.1 会话级Fixtures
```python
@pytest.fixture(scope="session")
def test_config():
    """Load test configuration (session scope)."""
    with open("config/test_config.yaml") as f:
        return yaml.safe_load(f)

@pytest.fixture(scope="session")
def ssh_dut(test_config):
    """SSH client for DUT (session scope)."""
    from utils.ssh_client import SSHClient
    dut_config = test_config["devices"]["dut"]
    with SSHClient(
        dut_config["ip"],
        dut_config["user"],
        dut_config["password"]
    ) as client:
        yield client
```

### 4.2 函数级Fixtures
```python
@pytest.fixture
def prometheus_client(test_config):
    """Prometheus client for each test."""
    from utils.prometheus_client import PrometheusClient
    return PrometheusClient(test_config["devices"]["monitor"]["prometheus_url"])
```

### 4.3 Fixture依赖
```python
@pytest.fixture
def nic_info(ssh_dut, test_config):
    """Get NIC information using SSH connection."""
    from utils.nic_helper import NICHelper
    nic_name = test_config["nics"][0]["name"]
    return NICHelper.get_nic_info(ssh_dut, nic_name)
```

## 5. 测试断言规范

### 5.1 带宽断言
```python
def test_bandwidth(target_bandwidth, measured_bandwidth, tolerance=0.05):
    """Assert bandwidth achievement."""
    min_bandwidth = target_bandwidth * (1 - tolerance)
    assert measured_bandwidth >= min_bandwidth, \
        f"Bandwidth {measured_bandwidth} Gbps below target {min_bandwidth} Gbps"
```

### 5.2 Error计数断言
```python
def test_nic_errors(nic_stats):
    """Assert no NIC errors."""
    assert nic_stats['rx_errors'] == 0, \
        f"RX errors detected: {nic_stats['rx_errors']}"
    assert nic_stats['tx_errors'] == 0, \
        f"TX errors detected: {nic_stats['tx_errors']}"
```

### 5.3 内存泄露断言
```python
def test_memory_leak(memory_before, memory_after, max_growth_percent=10):
    """Assert no memory leak."""
    growth_percent = ((memory_after - memory_before) / memory_before) * 100
    assert growth_percent <= max_growth_percent, \
        f"Memory growth {growth_percent}% exceeds threshold {max_growth_percent}%"
```

## 6. 测试数据参数化

### 6.1 使用pytest.mark.parametrize
```python
@pytest.mark.parametrize("bandwidth_target", ["50%", "70%", "80%", "90%"])
def test_stress_kernel_varying_bandwidth(bandwidth_target, ssh_dut):
    """Test stress with different bandwidth targets."""
    # Test implementation
    pass

@pytest.mark.parametrize("packet_size", ["64", "512", "1500", "64K"])
def test_stress_kernel_varying_packet_size(packet_size, ssh_dut):
    """Test stress with different packet sizes."""
    # Test implementation
    pass
```

### 6.2 使用fixture参数化
```python
@pytest.fixture(params=["kernel", "dpdk", "rdma"])
def driver_type(request):
    """Parametrize driver type."""
    return request.param

def test_multi_driver(driver_type):
    """Test runs for each driver type."""
    pass
```

## 7. 测试跳过和条件执行

### 7.1 跳过测试
```python
@pytest.mark.skip(reason="Hardware not available")
def test_hardware_specific():
    pass

@pytest.mark.skipif(
    not shutil.which("dpdk-devbind"),
    reason="DPDK not installed"
)
def test_dpdk_feature():
    pass
```

### 7.2 条件执行
```python
def test_kernel_only(test_config):
    """Test only for kernel driver."""
    if test_config["nics"][0]["driver"] != "kernel":
        pytest.skip("Only for kernel driver")
    # Test implementation
```

## 8. 测试报告生成

### 8.1 HTML报告
```bash
pytest --html=result/reports/report.html --self-contained-html
```

### 8.2 JUnit XML报告
```bash
pytest --junitxml=result/reports/junit.xml
```

### 8.3 覆盖率报告
```bash
pytest --cov=core --cov=testcase --cov=utils --cov-report=html:result/reports/coverage
```

## 9. 并行执行

### 9.1 使用pytest-xdist
```bash
# Run tests in parallel with 4 workers
pytest -n 4

# Run tests in parallel with auto-detected workers
pytest -n auto
```

### 9.2 标记分组执行
```bash
# Run only stress tests
pytest -m stress

# Run only kernel tests
pytest -m kernel

# Run only P0 priority tests
pytest -m p0

# Exclude slow tests
pytest -m "not slow"
```

## 10. 测试运行命令参考

### 10.1 基本执行
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with very verbose output
pytest -vv
```

### 10.2 特定测试执行
```bash
# Run specific test file
pytest tests/test_stress_kernel.py

# Run specific test function
pytest tests/test_stress_kernel.py::test_stress_kernel_tcp_80percent

# Run specific test class
pytest tests/test_stress_kernel.py::TestKernelStress
```

### 10.3 调试执行
```bash
# Run with debugger on failure
pytest --pdb

# Run with traceback on failure
pytest --tb=long

# Run showing local variables on failure
pytest --showlocals
```

## 11. 最佳实践

1. **每个测试函数只做一件事**：保持测试函数简单、专注
2. **使用描述性的测试名称**：从函数名就能知道测试目的
3. **使用fixtures减少重复代码**：共享的setup/teardown放在fixtures
4. **使用适当的scope**：session/scope/module/function选择合适的fixture scope
5. **记录关键断言信息**：使用pytest的assertion introspection
6. **清理测试数据**：确保teardown正确执行，不留下测试数据
7. **使用标记分类测试**：便于选择性执行
8. **编写测试文档**：每个测试函数添加docstring说明测试目的

---

*文档版本: 1.0*
*更新日期: 2026-04-21*
```

- [ ] **Step 2: Commit**

```bash
git add docs/pytest-guidelines.md
git commit -m "docs: add pytest guidelines documentation"
```

---

## 执行计划总结

### 已完成交付物

1. **✅ Excel用例清单**: `testcase_list.xlsx` (50个用例)
2. **✅ Pytest规范文档**: `docs/pytest-guidelines.md`
3. **✅ 实施计划文档**: `.sisyphus/plans/YYYY-MM-DD-nic-test-implementation.md`

### 下一步行动

**Review通过后开始编码实施**:
1. 实现SSH客户端工具
2. 实现Prometheus监控客户端
3. 实现NIC工具类
4. 实现测试基类和框架
5. 实现各测试类型用例（压力/长时间/异常/混合/业务流）
6. 实现报告生成器
7. 实现Jenkins集成脚本

---

**计划文档已保存至**: `.sisyphus/plans/2026-04-21-nic-test-implementation.md`

**是否开始执行实施计划？**