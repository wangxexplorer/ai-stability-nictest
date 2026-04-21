#!/usr/bin/env python3
"""Generate testcase_list.xlsx from review document."""
import pandas as pd
from pathlib import Path


def generate_stress_test_cases():
    """Generate stress test cases."""
    cases = [
        # Kernel TCP Stress Tests
        ("ST-001", "Kernel快速基准验证-80%带宽", "kernel", "30min", "80%", "1500B", "TCP", 1, "iperf3", "P1", "必选"),
        ("ST-002", "Kernel标准压力测试-80%带宽-16流", "kernel", "1h", "80%", "1500B", "TCP", 16, "iperf3", "P1", "必选"),
        ("ST-003", "Kernel高压压力测试-90%带宽", "kernel", "4h", "90%", "1500B", "TCP", 16, "iperf3", "P1", "必选"),
        ("ST-004", "Kernel小包PPS极限测试-64B", "kernel", "4h", "80%", "64B", "TCP", 32, "iperf3", "P1", "必选"),
        ("ST-005", "Kernel大包带宽测试-64KB", "kernel", "4h", "80%", "64KB", "TCP", 8, "iperf3", "P1", "必选"),
        ("ST-006", "Kernel Jumbo Frame测试-9000B", "kernel", "1h", "80%", "9000B", "TCP", 8, "iperf3", "P1", "必选"),
        ("ST-007", "Kernel极高带宽测试-95%", "kernel", "1h", "95%", "1500B", "TCP", 16, "iperf3", "P1", "必选"),
        ("ST-008", "Kernel长压力测试-24h", "kernel", "24h", "80%", "1500B", "TCP", 8, "iperf3", "P1", "必选"),
        # Kernel UDP Stress Tests
        ("ST-009", "Kernel UDP带宽测试-80%", "kernel", "1h", "80%", "1500B", "UDP", 16, "iperf3 -u", "P1", "必选"),
        ("ST-010", "Kernel UDP丢包测试-小包", "kernel", "4h", "80%", "64B", "UDP", 32, "iperf3 -u", "P1", "必选"),
        ("ST-011", "Kernel UDP PPS极限测试-64B高频", "kernel", "4h", "90%", "64B", "UDP", 64, "iperf3 -u", "P1", "必选"),
        # DPDK Stress Tests
        ("ST-012", "DPDK标准压力测试", "dpdk", "4h", "80%", "1500B", "-", 16, "pktgen", "P1", "必选"),
        ("ST-013", "DPDK小包PPS测试", "dpdk", "4h", "80%", "64B", "-", 32, "pktgen", "P1", "必选"),
        ("ST-014", "DPDK高压测试-90%", "dpdk", "1h", "90%", "1500B", "-", 16, "pktgen", "P1", "必选"),
        # RDMA Stress Tests (256 QP, bidirectional)
        ("ST-015", "RDMA Write双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_write_bw -b", 256, "perftest", "P1", "必选"),
        ("ST-016", "RDMA Read双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_read_bw -b", 256, "perftest", "P1", "必选"),
        ("ST-017", "RDMA Send双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_send_bw -b", 256, "perftest", "P1", "必选"),
        ("ST-018", "RDMA Write延迟测试-256QP", "rdma", "30min", "-", "-", "ib_write_lat", 256, "perftest", "P1", "必选"),
    ]
    return cases


def main():
    """Generate testcase_list.xlsx."""
    stress_cases = generate_stress_test_cases()
    
    df = pd.DataFrame(
        stress_cases,
        columns=["用例ID", "用例名称", "驱动类型", "时长", "带宽目标", "包大小", 
                "协议", "并发流", "流量工具", "优先级", "必选/可选"]
    )
    
    df["用例类型"] = "stress"
    df["对应Python文件"] = "testcase/stress_test.py"
    df["状态"] = "active"
    df["负责人"] = ""
    df["最后更新时间"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    output_path = Path(__file__).parent.parent / "testcase_list.xlsx"
    df.to_excel(output_path, index=False, sheet_name="TestCases")
    
    print(f"Generated testcase_list.xlsx with {len(df)} test cases")
    print(f"Location: {output_path}")


if __name__ == "__main__":
    main()
