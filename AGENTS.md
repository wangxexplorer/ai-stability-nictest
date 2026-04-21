# NIC Stability Test System - AGENTS.md

## 1. 项目概述

本项目是一个网卡（NIC）稳定性自动化测试系统，用于验证网卡在高负载、长时间运行等场景下的稳定性表现。

### 核心功能
1. **自动化执行**：批量执行多种稳定性测试用例（压力测试、长时间测试、异常测试、混合数据测试、业务流测试等）
2. **结果分析**：自动收集测试结果，进行统计分析并生成报告
3. **日志管理**：结构化保存测试日志，支持故障追溯
4. **CI/CD集成**：通过Jenkins流水线触发，支持持续集成

### 测试用例类型
- **压力测试**：高并发数据传输、大流量冲击
- **长时间测试**：7x24小时持续运行监控
- **异常测试**：链路中断、热插拔、驱动重启等场景
- **混合数据测试**：多种数据类型/大小混合传输验证
- **业务流测试**：模拟真实业务场景的端到端测试

*注：测试类型可扩展，新增类型需在testcase_list.xlsx、pytest标记和项目结构中同步添加*

---

## 2. 技术栈

### 核心语言
- **Python 3.9+**：主要开发语言

### 主要依赖
```
pytest>=7.0.0          # 测试框架
pyyaml>=6.0            # YAML配置解析
jinja2>=3.0            # 报告模板
requests>=2.28.0       # HTTP API通信
paramiko>=2.11.0       # SSH远程执行
psutil>=5.9.0          # 系统资源监控
pandas>=1.5.0          # 数据分析
matplotlib>=3.6.0      # 图表生成
python-json-logger>=2.0.0  # JSON格式日志
```

### Jenkins集成
- **流水线脚本**：使用Jenkinsfile（Declarative Pipeline）
- **触发方式**：
  - 定时触发（ nightly build ）
  - Webhook触发（代码提交）
  - 手动触发
- **节点配置**：支持Master-Agent分布式执行

---

## 3. 编码规范

### Python代码规范（PEP 8）

#### 基础规范
- **缩进**：4个空格，禁止使用Tab
- **行长度**：最大79字符（文档字符串/注释72字符）
- **编码**：UTF-8
- **换行符**：Unix风格（LF）

#### 命名规范
| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | 小写+下划线 | `nic_test`, `result_analyzer` |
| 类 | 大驼峰 | `NicStabilityTest`, `TestRunner` |
| 函数/方法 | 小写+下划线 | `run_test_case()`, `analyze_results()` |
| 常量 | 大写+下划线 | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| 私有成员 | 前缀下划线 | `_internal_method()`, `_config` |

#### 导入规范
```python
# 标准库
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# 第三方库
import pytest
import yaml
from paramiko import SSHClient

# 项目内部
from testcase.base import BaseTestCase
from utils.logger import get_logger
```

#### 文档字符串规范
```python
def run_stability_test(duration: int, nic_interface: str) -> dict:
    """执行网卡稳定性测试。

    在指定网卡接口上运行长时间稳定性测试，监控丢包率、
    延迟抖动、吞吐量等关键指标。

    Args:
        duration: 测试持续时间（秒）
        nic_interface: 网卡接口名称，如 "eth0"

    Returns:
        包含测试结果的字典，结构如下：
        {
            "status": "passed" | "failed",
            "metrics": {
                "packet_loss_rate": float,
                "avg_latency_ms": float,
                "throughput_mbps": float
            },
            "logs": List[str]
        }

    Raises:
        NicNotFoundError: 指定网卡不存在
        TestTimeoutError: 测试执行超时
    """
```

#### 类型注解
```python
from typing import Dict, List, Optional, Tuple

def calculate_statistics(
    data_points: List[float],
    precision: int = 2
) -> Tuple[float, float, float]:
    """计算统计数据。

    Returns:
        Tuple of (mean, min, max)
    """
    ...
```

### 日志规范
- 使用结构化JSON日志，便于ELK等系统采集
- 日志级别：DEBUG < INFO < WARNING < ERROR < CRITICAL
- 关键操作必须记录：测试开始/结束、异常、性能指标

### Pytest测试用例设计规范

#### 测试文件组织
- **位置**：所有单元测试放在 `tests/` 目录，与源码目录结构保持一致
- **命名**：测试文件以 `test_` 开头，如 `test_runner.py`
- **测试函数**：以 `test_` 开头，命名清晰描述测试场景

#### 测试用例编写原则
```python
# tests/test_monitor.py
import pytest
from core.monitor import SystemMonitor


class TestSystemMonitor:
    """系统监控模块测试类。"""

    def test_get_cpu_usage_returns_valid_percentage(self):
        """测试获取CPU使用率返回有效百分比值。"""
        monitor = SystemMonitor()
        cpu_usage = monitor.get_cpu_usage()

        assert isinstance(cpu_usage, float)
        assert 0.0 <= cpu_usage <= 100.0

    def test_get_memory_usage_raises_exception_when_service_down(self):
        """测试服务不可用时获取内存使用率抛出异常。"""
        monitor = SystemMonitor()

        with pytest.raises(RuntimeError, match="Monitor service unavailable"):
            monitor.get_memory_usage()

    @pytest.mark.parametrize("duration,expected", [
        (60, 1),
        (300, 5),
        (3600, 60),
    ])
    def test_calculate_sample_count(self, duration, expected):
        """测试采样次数计算。"""
        monitor = SystemMonitor(sample_interval=60)
        assert monitor.calculate_sample_count(duration) == expected
```

#### Fixture规范
```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_nic_interface():
    """提供模拟网卡接口的fixture。"""
    mock = MagicMock()
    mock.name = "eth0"
    mock.is_up = True
    mock.speed = 1000
    return mock

@pytest.fixture(scope="function")
def temp_test_dir(tmp_path):
    """为每个测试函数提供临时目录。"""
    return tmp_path / "test_run"

@pytest.fixture(scope="module")
def shared_test_data():
    """模块级别fixture，数据在模块内测试共享。"""
    return {"initialized": True, "data": []}
```

#### 测试标记使用
```python
import pytest

@pytest.mark.stress          # 压力测试
@pytest.mark.longevity       # 长时间测试
@pytest.mark.anomaly         # 异常测试
@pytest.mark.mixed_data      # 混合数据测试
@pytest.mark.business_flow   # 业务流测试
def test_network_throughput_under_load():
    """测试高负载下网络吞吐量。"""
    pass
```

#### Mock使用规范
```python
from unittest.mock import patch, MagicMock, mock_open

class TestNicHelper:
    """网卡工具测试。"""

    @patch("utils.nic_helper.subprocess.run")
    def test_get_nic_info_with_mocked_subprocess(self, mock_run):
        """使用mock测试获取网卡信息。"""
        mock_run.return_value = MagicMock(
            stdout="eth0: flags=4163<UP,BROADCAST>\n",
            returncode=0
        )

        result = get_nic_info("eth0")
        assert result["name"] == "eth0"
        assert result["status"] == "up"
        mock_run.assert_called_once_with(
            ["ifconfig", "eth0"],
            capture_output=True,
            text=True
        )

    def test_read_config_with_mocked_file(self):
        """测试配置文件读取。"""
        mock_data = '{"timeout": 30, "retry": 3}'
        with patch("builtins.open", mock_open(read_data=mock_data)):
            config = read_config("/fake/path.json")
            assert config["timeout"] == 30
```

#### 测试断言最佳实践
| 场景 | 推荐方式 |
|------|----------|
| 相等判断 | `assert actual == expected` |
| 异常抛出 | `pytest.raises(ExceptionType)` |
| 列表包含 | `assert item in collection` |
| 近似相等 | `assert abs(a - b) < 0.001` |
| Mock调用 | `mock.assert_called_once_with(...)` |

#### 运行测试命令
```bash
# 运行所有测试
pytest

# 运行特定模块
pytest tests/test_monitor.py

# 运行特定测试
pytest tests/test_monitor.py::TestSystemMonitor::test_get_cpu_usage

# 运行特定标记的测试
pytest -m "stress"            # 只运行压力测试
pytest -m "longevity"         # 只运行长时间测试
pytest -m "anomaly"           # 只运行异常测试
pytest -m "mixed_data"        # 只运行混合数据测试
pytest -m "business_flow"     # 只运行业务流测试

# 生成覆盖率报告
pytest --cov=core --cov=utils --cov-report=html

# 详细输出
pytest -v --tb=short
```

---

## 4. 项目结构

```
nic-stability-test/
├── AGENTS.md                    # 本项目文档
├── README.md                    # 项目说明
├── requirements.txt             # Python依赖
├── setup.py                     # 包安装配置
├── Jenkinsfile                  # Jenkins流水线定义
├── config/
│   ├── test_config.yaml         # 测试参数配置
│   ├── jenkins_config.yaml      # Jenkins节点配置
│   └── logging_config.yaml      # 日志配置
├── testcase/                    # 测试用例目录
│   ├── __init__.py
│   ├── base.py                  # 测试基类
│   ├── stress_test.py           # 压力测试用例
│   ├── longevity_test.py        # 长时间稳定性测试
│   ├── anomaly_test.py          # 异常测试用例
│   ├── mixed_data_test.py       # 混合数据测试用例
│   └── business_flow_test.py    # 业务流测试用例
# 新增测试类型：在此处添加新的测试用例文件
├── core/                        # 核心框架
│   ├── __init__.py
│   ├── runner.py                # 测试执行引擎
│   ├── scheduler.py             # 测试调度器
│   ├── monitor.py               # 系统资源监控
│   └── reporter.py              # 报告生成器
├── utils/                       # 工具模块
│   ├── __init__.py
│   ├── logger.py                # 日志工具
│   ├── nic_helper.py            # 网卡操作工具
│   ├── ssh_client.py            # SSH远程执行
│   └── validators.py            # 数据验证工具
├── result/                      # 测试结果目录（.gitignore）
│   ├── raw/                     # 原始测试数据
│   ├── reports/                 # 生成报告
│   ├── logs/                    # 测试日志
│   └── archives/                # 归档数据
├── tests/                       # 单元测试
│   ├── __init__.py
│   ├── test_runner.py
│   ├── test_monitor.py
│   └── fixtures/                # 测试固件
└── scripts/                     # 辅助脚本
    ├── setup_env.sh             # 环境初始化
    ├── run_tests.sh             # 本地执行脚本
    └── archive_results.sh       # 结果归档
```

---

## 5. 关键设计说明

### 测试执行流程
```
Jenkins触发 → 环境检查 → 测试调度 → 并行执行 → 结果收集 → 分析报告 → 归档存储
```

### 扩展性设计
- **插件机制**：新测试用例继承 `BaseTestCase`，自动注册到调度器
- **配置驱动**：测试参数外置YAML，无需修改代码调整策略
- **多节点支持**：通过SSHClient支持分布式测试执行

### 可靠性保障
- 每个测试用例独立超时控制
- 异常捕获与自动重试机制
- 测试失败自动保留现场日志
- 资源清理保证（try-finally/上下文管理器）

---

## 6. 快速开始

### 本地开发环境
```bash
# 1. 克隆代码
git clone <repo-url>
cd nic-stability-test

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
pip install -e .

# 4. 运行测试
python -m pytest tests/
```

### Jenkins配置
1. 创建Pipeline类型任务
2. 配置Git仓库地址
3. 指定Jenkinsfile路径
4. 配置定时触发器（如 `H 2 * * *` 每日2点）

---

## 7. 维护者须知

### 添加新测试用例
1. 在 `testcase/` 下创建新文件，继承 `BaseTestCase`
2. 实现 `setup()`, `run()`, `teardown()`, `validate()` 方法
3. 在 `config/test_config.yaml` 中添加用例配置
4. **更新 `testcase/testcase_list.xlsx`**：在Excel清单中添加新用例信息（用例ID、名称、描述、负责人、状态等）
5. 补充单元测试到 `tests/`

### 测试用例清单（testcase_list.xlsx）
- **用途**：供测试管理人员查看和维护，包含所有测试用例的元信息
- **格式**：Excel (.xlsx)
- **必含字段**：
  - `用例ID`：唯一标识（如 TC001, TC002）
  - `用例名称`：简短描述
  - `用例类型`：stress/longevity/anomaly/mixed_data/business_flow（可扩展，新增类型需同步更新testcase_list.xlsx、pytest标记和项目结构）
  - `对应Python文件`：`testcase/xxx_test.py`
  - `测试目的`：详细描述验证目标
  - `执行时长`：预计执行时间
  - `优先级`：P0/P1/P2
  - `负责人`：开发和维护人员
  - `状态`：active/inactive/deprecated
  - `最后更新时间`：日期
- **同步机制**：代码合并时同步更新Excel，CI检查清单与代码一致性

### 修改编码规范
如需调整PEP 8相关规范，必须：
1. 更新本文件第3节
2. 同步更新 `setup.cfg` 或 `pyproject.toml` 中的linter配置
3. 全量代码重构以符合新规
4. 通知所有协作者

---

*Last Updated: 2026-04-21*
*Maintainer: NIC Test Team*
