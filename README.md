# NIC稳定性测试系统

一个全面的网卡（NIC）稳定性自动化测试系统，用于验证网卡在高负载、长时间运行等场景下的稳定性表现。

## 📋 功能特性

### 测试类型
- **压力测试 (Stress Test)**：高并发数据传输、大流量冲击验证
- **长时间测试 (Longevity Test)**：7x24小时持续运行监控
- **异常测试 (Anomaly Test)**：链路中断、驱动重启、DDoS攻击等场景
- **混合数据测试 (Mixed Data Test)**：多种数据类型/大小混合传输验证
- **业务流测试 (Business Flow Test)**：模拟真实业务场景的端到端测试

### 核心特性
- **多驱动支持**：支持 kernel、DPDK、RDMA 三种驱动类型
- **多网卡规格**：支持 10G/25G/40G/100G 等多种网卡规格
- **Prometheus监控**：集成 Prometheus + node_exporter 实时监控系统指标
- **自动化执行**：基于 pytest 的自动化测试框架
- **丰富的报告**：支持 JSON/HTML 格式的测试报告生成
- **Excel用例管理**：完整的用例清单管理 (testcase_list.xlsx)

## 🏗️ 项目结构

```
nic-stability-test/
├── AGENTS.md                    # AI Agent 规范文档
├── README.md                    # 项目说明文档（本文件）
├── requirements.txt             # Python依赖
├── testcase_list.xlsx           # 测试用例清单（50个用例）
│
├── config/                      # 配置文件
│   └── test_config.yaml         # 测试参数配置
│
├── testcase/                    # 测试用例实现
│   ├── base.py                  # 测试基类（所有用例继承此类）
│   ├── stress_test.py           # 压力测试用例
│   ├── longevity_test.py        # 长时间测试用例（待实现）
│   ├── anomaly_test.py          # 异常测试用例（待实现）
│   ├── mixed_data_test.py        # 混合数据测试用例（待实现）
│   └── business_flow_test.py    # 业务流测试用例（待实现）
│
├── core/                        # 核心框架
│   ├── runner.py                # 测试执行引擎
│   └── reporter.py              # 报告生成器
│
├── utils/                       # 工具模块
│   ├── ssh_client.py            # SSH远程执行
│   ├── prometheus_client.py     # Prometheus监控客户端
│   └── nic_helper.py            # 网卡操作工具
│
├── tests/                       # 单元测试
│   └── conftest.py              # pytest配置和fixtures
│
├── scripts/                     # 辅助脚本
│   └── generate_testcase_excel.py  # Excel用例清单生成器
│
└── result/                      # 测试结果目录
    ├── raw/                     # 原始测试数据
    ├── reports/                 # 生成报告
    ├── logs/                    # 测试日志
    └── archives/                # 归档数据
```

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Linux 操作系统（测试执行环境）
- SSH 访问权限（DUT/Tester/Monitor 设备）
- Prometheus + node_exporter（监控服务）

### 安装依赖

```bash
# 1. 克隆代码
git clone <repo-url>
cd nic-stability-test

# 2. 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 配置测试环境

编辑 `config/test_config.yaml`：

```yaml
# 设备连接信息
devices:
  dut:
    ip: "192.168.1.10"          # DUT设备IP
    user: "root"
    password: "your_password"
  tester:
    ip: "192.168.1.11"          # Tester设备IP
    user: "root"
    password: "your_password"
  monitor:
    ip: "192.168.1.12"          # Monitor设备IP
    prometheus_url: "http://192.168.1.12:9090"

# 网卡配置
nics:
  - name: "eth0"
    pci: "0000:01:00.0"
    driver: "kernel"            # kernel/dpdk/rdma
    speed: "25G"
```

### 运行测试

```bash
# 运行所有压力测试
pytest testcase/stress_test.py -v

# 运行特定标记的测试
pytest -m "stress"              # 只运行压力测试
pytest -m "kernel"              # 只运行kernel驱动测试
pytest -m "longevity"           # 只运行长时间测试

# 生成HTML报告
pytest --html=result/reports/report.html --self-contained-html

# 生成覆盖率报告
pytest --cov=core --cov=utils --cov-report=html
```

## 📊 测试用例清单

完整的测试用例清单请查看 `testcase_list.xlsx`，包含50个测试用例：

| 测试类型 | 用例数量 | 说明 |
|---------|---------|------|
| 压力测试 | 18个 | kernel/dpdk/rdma驱动全覆盖 |
| 长时间测试 | 6个 | 7x24小时持续运行测试 |
| 异常测试 | 14个 | 链路中断、DDoS、队列配置变更等 |
| 混合数据测试 | 6个 | 包大小混合、协议混合 |
| 业务流测试 | 6个 | Web服务、数据库、存储场景 |

## 🏢 测试拓扑

```
┌─────────────┐          ┌─────────────┐
│  Controller │          │   Monitor   │
│  (本机)     │◄────────►│ (Prometheus)│
└──────┬──────┘          └──────┬──────┘
       │                         │
       │ SSH                     │ 指标采集
       ▼                         ▼
┌─────────────┐          ┌─────────────┐
│     DUT     │◄─流量───►│    Tester   │
│  (被测端)   │          │  (发送端)   │
│  eth0/eth1  │          │  eth0/eth1  │
└─────────────┘          └─────────────┘
```

- **DUT**：被测设备，运行目标网卡
- **Tester**：测试发起设备，发送测试流量
- **Monitor**：监控节点，Prometheus服务器
- **Controller**：测试控制节点（本机）

## 📝 配置说明

### 驱动类型配置

支持三种驱动类型，在 `config/test_config.yaml` 中配置：

| 驱动类型 | 流量工具 | 说明 |
|---------|---------|------|
| kernel | iperf3 | 标准内核网络栈 |
| dpdk | pktgen | DPDK高性能数据平面 |
| rdma | perftest | RDMA远程直接内存访问 |

### 网卡规格配置

支持多种网卡规格，带宽目标会自动计算：

| 网卡规格 | 标准压力测试目标 | 长时间测试目标 |
|---------|-----------------|---------------|
| 10G | 8 Gbps (80%) | 7 Gbps (70%) |
| 25G | 20 Gbps (80%) | 17.5 Gbps (70%) |
| 40G | 32 Gbps (80%) | 28 Gbps (70%) |
| 100G | 80 Gbps (80%) | 70 Gbps (70%) |

## 🔍 验证指标

所有测试类型都会验证以下指标：

| 指标 | 采集方式 | 说明 |
|-----|---------|------|
| 带宽吞吐量 | iperf3/pktgen/perftest | 实测带宽 vs 目标带宽比例 |
| 丢包率 | iperf3统计、网卡统计 | 数据包丢失比例 |
| 延迟/延迟抖动 | iperf3/perftest延迟输出 | 数据传输延迟和抖动 |
| CPU使用率 | Prometheus node_exporter | DUT网卡处理CPU负载 |
| **内存增长** | Prometheus node_exporter | **内存泄露检测（关键）** |
| **网卡error计数** | /sys/class/net/统计 | **网卡错误计数（关键）** |

## 🔧 扩展开发

### 添加新测试用例

1. 在 `testcase/` 下创建新的测试文件
2. 继承 `BaseTestCase` 基类
3. 实现 `setup()`, `run()`, `teardown()`, `validate()` 方法
4. 在 `testcase_list.xlsx` 中添加用例信息
5. 添加 pytest 标记：`@pytest.mark.xxx`

示例：

```python
import pytest
from testcase.base import BaseTestCase

@pytest.mark.stress
@pytest.mark.kernel
class TestMyNewTest:
    """我的新测试用例。"""
    
    def test_my_test(self):
        """测试我的新功能。"""
        config = {
            'test_id': 'ST-999',
            'test_name': '我的新测试',
            'duration': '1h',
            'driver': 'kernel'
        }
        test = MyTestClass(config)
        result = test.execute()
        assert result['passed']
```

### 添加新驱动类型

1. 在 `config/test_config.yaml` 中添加驱动配置
2. 在 `utils/` 中添加驱动操作工具类
3. 在测试用例中添加驱动类型标记

## 🐛 调试与故障排查

### 日志查看

测试日志保存在 `result/logs/` 目录：

```bash
# 查看最新日志
tail -f result/logs/latest.log
```

### 常见问题

1. **SSH连接失败**：检查设备IP、用户名、密码配置
2. **Prometheus查询失败**：检查Prometheus服务状态和URL配置
3. **网卡未找到**：检查网卡名称和PCI地址配置
4. **测试超时**：检查网络连通性和防火墙设置

## 📚 相关文档

- **AGENTS.md** - AI Agent 开发规范文档
- **testcase_list.xlsx** - 完整测试用例清单（50个用例）
- `.sisyphus/drafts/nic-test-design.md` - 设计决策记录
- `.sisyphus/plans/2026-04-21-nic-test-implementation.md` - 实施计划

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/my-feature`
3. 提交更改：`git commit -am 'feat: add new feature'`
4. 推送分支：`git push origin feature/my-feature`
5. 创建 Pull Request

## 📄 许可证

[MIT License](LICENSE)

## 👥 维护者

- NIC Test Team

---

*最后更新：2026-04-21*
