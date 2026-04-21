#!/usr/bin/env python3
"""Generate testcase_list.xlsx from review document."""
import pandas as pd
from pathlib import Path


def generate_stress_test_cases():
    """Generate stress test cases (18个)."""
    cases = [
        # Kernel TCP Stress Tests (8个)
        ("ST-001", "Kernel快速基准验证-80%带宽", "kernel", "30min", "80%", "1500B", "TCP", 1, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-002", "Kernel标准压力测试-80%带宽-16流", "kernel", "1h", "80%", "1500B", "TCP", 16, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-003", "Kernel高压压力测试-90%带宽", "kernel", "4h", "90%", "1500B", "TCP", 16, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-004", "Kernel小包PPS极限测试-64B", "kernel", "4h", "80%", "64B", "TCP", 32, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-005", "Kernel大包带宽测试-64KB", "kernel", "4h", "80%", "64KB", "TCP", 8, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-006", "Kernel Jumbo Frame测试-9000B", "kernel", "1h", "80%", "9000B", "TCP", 8, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-007", "Kernel极高带宽测试-95%", "kernel", "1h", "95%", "1500B", "TCP", 16, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-008", "Kernel长压力测试-24h", "kernel", "24h", "80%", "1500B", "TCP", 8, "iperf3", "P1", "必选", "stress", "testcase/stress_test.py"),
        # Kernel UDP Stress Tests (3个)
        ("ST-009", "Kernel UDP带宽测试-80%", "kernel", "1h", "80%", "1500B", "UDP", 16, "iperf3 -u", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-010", "Kernel UDP丢包测试-小包", "kernel", "4h", "80%", "64B", "UDP", 32, "iperf3 -u", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-011", "Kernel UDP PPS极限测试-64B高频", "kernel", "4h", "90%", "64B", "UDP", 64, "iperf3 -u", "P1", "必选", "stress", "testcase/stress_test.py"),
        # DPDK Stress Tests (3个)
        ("ST-012", "DPDK标准压力测试", "dpdk", "4h", "80%", "1500B", "-", 16, "pktgen", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-013", "DPDK小包PPS测试", "dpdk", "4h", "80%", "64B", "-", 32, "pktgen", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-014", "DPDK高压测试-90%", "dpdk", "1h", "90%", "1500B", "-", 16, "pktgen", "P1", "必选", "stress", "testcase/stress_test.py"),
        # RDMA Stress Tests (4个) - 256 QP, 双向
        ("ST-015", "RDMA Write双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_write_bw -b", 256, "perftest", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-016", "RDMA Read双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_read_bw -b", 256, "perftest", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-017", "RDMA Send双向带宽测试-256QP", "rdma", "1h", "80%", "-", "ib_send_bw -b", 256, "perftest", "P1", "必选", "stress", "testcase/stress_test.py"),
        ("ST-018", "RDMA Write延迟测试-256QP", "rdma", "30min", "-", "-", "ib_write_lat", 256, "perftest", "P1", "必选", "stress", "testcase/stress_test.py"),
    ]
    return cases


def generate_longevity_test_cases():
    """Generate longevity test cases (6个)."""
    cases = [
        # Kernel Longevity Tests (3个)
        ("LT-001", "Kernel快速长时测试-24h", "kernel", "24h", "75%", "1500B", "TCP", 8, "iperf3", "P1", "必选", "longevity", "testcase/longevity_test.py"),
        ("LT-002", "Kernel标准长时测试-7x24h", "kernel", "168h", "75%", "1500B", "TCP", 8, "iperf3", "P1", "必选", "longevity", "testcase/longevity_test.py"),
        ("LT-003", "Kernel深度长时测试-15天", "kernel", "360h", "75%", "1500B", "TCP", 8, "iperf3", "P2", "必选", "longevity", "testcase/longevity_test.py"),
        # DPDK Longevity Tests (1个)
        ("LT-004", "DPDK标准长时测试-7x24h", "dpdk", "168h", "75%", "1500B", "-", 8, "pktgen", "P1", "必选", "longevity", "testcase/longevity_test.py"),
        # RDMA Longevity Tests (1个)
        ("LT-005", "RDMA标准长时测试-7x24h", "rdma", "168h", "75%", "-", "ib_write_bw", 1, "perftest", "P1", "必选", "longevity", "testcase/longevity_test.py"),
        # Special Longevity Tests (1个)
        ("LT-006", "Kernel周期波动流量测试", "kernel", "168h", "50%~90%波动", "1500B", "TCP", 8, "iperf3", "P2", "可选", "longevity", "testcase/longevity_test.py"),
    ]
    return cases


def generate_anomaly_test_cases():
    """Generate anomaly test cases (14个)."""
    cases = [
        # Kernel Anomaly Tests (9个)
        ("AN-001", "Kernel链路中断测试", "kernel", "链路中断", "ifconfig down/up", "链路UP+流量恢复30s", "-", "-", "-", "P0", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-002", "Kernel驱动重启测试", "kernel", "驱动重启", "modprobe -r/r driver", "驱动可用+流量恢复30s", "-", "-", "-", "P0", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-003", "Kernel流量突发测试", "kernel", "流量突发", "瞬时90%带宽高压", "流量稳定", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-004", "Kernel SYN Flood攻击", "kernel", "DDoS攻击", "hping3 -S flood", "攻击结束流量恢复", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-005", "Kernel UDP Flood攻击", "kernel", "DDoS攻击", "hping3 -2 flood", "攻击结束流量恢复", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-006", "Kernel畸形包测试-超大包", "kernel", "畸形包", "tcpreplay oversized packet", "error记录", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-007", "Kernel畸形包测试-超小包", "kernel", "畸形包", "tcpreplay undersize packet", "error记录", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-008", "Kernel小包PPS攻击", "kernel", "小包攻击", "iperf3 -u -l 64 -P 64", "流量恢复", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-009", "Kernel队列数和队列深度组合测试", "kernel", "队列配置变更", "ethtool修改队列数/深度组合", "流量稳定+error计数", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        # DPDK Anomaly Tests (4个)
        ("AN-010", "DPDK链路中断测试", "dpdk", "链路中断", "ifconfig down/up", "DPDK重初始化+流量恢复", "-", "-", "-", "P0", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-011", "DPDK驱动重启测试", "dpdk", "驱动重启", "DPDK rebind/reinit", "DPDK可用+流量恢复", "-", "-", "-", "P0", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-012", "DPDK SYN Flood攻击", "dpdk", "DDoS攻击", "hping3 -S flood", "应用层恢复", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        ("AN-013", "DPDK小包PPS攻击", "dpdk", "小包攻击", "pktgen high PPS", "流量恢复", "-", "-", "-", "P1", "必选", "anomaly", "testcase/anomaly_test.py"),
        # RDMA Anomaly Tests (1个, 可选)
        ("AN-014", "RDMA异常恢复测试", "rdma", "RDMA异常", "QP状态异常恢复", "QP状态恢复", "-", "-", "-", "P2", "可选", "anomaly", "testcase/anomaly_test.py"),
    ]
    return cases


def generate_mixed_data_test_cases():
    """Generate mixed data test cases (6个)."""
    cases = [
        # Kernel Mixed Data Tests (3个)
        ("MX-001", "Kernel包大小混合测试", "kernel", "包大小混合", "64B(20%)+512B(30%)+1500B(40%)+64KB(10%)", "4h", "iperf3多流", "-", "-", "P1", "必选", "mixed_data", "testcase/mixed_data_test.py"),
        ("MX-002", "Kernel协议混合测试", "kernel", "协议混合", "TCP(60%)+UDP(40%)", "4h", "iperf3 TCP+UDP", "-", "-", "P1", "必选", "mixed_data", "testcase/mixed_data_test.py"),
        ("MX-003", "Kernel全混合测试", "kernel", "包大小+协议混合", "包大小混合+协议混合", "4h", "iperf3多流", "-", "-", "P1", "必选", "mixed_data", "testcase/mixed_data_test.py"),
        # DPDK Mixed Data Tests (3个)
        ("MX-004", "DPDK包大小混合测试", "dpdk", "包大小混合", "64B(20%)+512B(30%)+1500B(40%)+64KB(10%)", "4h", "pktgen", "-", "-", "P1", "必选", "mixed_data", "testcase/mixed_data_test.py"),
        ("MX-005", "DPDK协议混合测试", "dpdk", "协议混合", "TCP(60%)+UDP(40%)模拟", "4h", "pktgen", "-", "-", "P1", "必选", "mixed_data", "testcase/mixed_data_test.py"),
        ("MX-006", "DPDK全混合测试", "dpdk", "包大小+协议混合", "包大小混合+协议混合", "4h", "pktgen", "-", "-", "P1", "必选", "mixed_data", "testcase/mixed_data_test.py"),
    ]
    return cases


def generate_business_flow_test_cases():
    """Generate business flow test cases (6个)."""
    cases = [
        # Required Business Flow Tests (3个)
        ("BF-001", "Web服务业务流测试", "kernel", "Web服务", "nginx", "ab/curl", "4h", "-", "-", "P1", "必选", "business_flow", "testcase/business_flow_test.py"),
        ("BF-002", "数据库业务流测试", "kernel", "数据库", "MySQL", "sysbench", "4h", "-", "-", "P1", "必选", "business_flow", "testcase/business_flow_test.py"),
        ("BF-003", "存储业务流测试", "kernel", "存储", "NFS Server", "fio", "4h", "-", "-", "P1", "必选", "business_flow", "testcase/business_flow_test.py"),
        # Optional Business Flow Tests (3个)
        ("BF-004", "视频流业务流测试", "kernel", "视频流", "nginx-rtmp", "ffmpeg", "4h", "-", "-", "P2", "可选", "business_flow", "testcase/business_flow_test.py"),
        ("BF-005", "消息队列业务流测试", "kernel", "消息队列", "Kafka", "producer/consumer", "4h", "-", "-", "P2", "可选", "business_flow", "testcase/business_flow_test.py"),
        ("BF-006", "微服务RPC业务流测试", "kernel", "微服务", "gRPC Server", "ghz", "4h", "-", "-", "P2", "可选", "business_flow", "testcase/business_flow_test.py"),
    ]
    return cases


def main():
    """Generate complete testcase_list.xlsx with all 50 test cases."""
    all_cases = []
    
    # 1. Stress Test Cases (18个)
    stress_cases = generate_stress_test_cases()
    for case in stress_cases:
        all_cases.append(case)
    
    # 2. Longevity Test Cases (6个)
    longevity_cases = generate_longevity_test_cases()
    for case in longevity_cases:
        all_cases.append(case)
    
    # 3. Anomaly Test Cases (14个)
    anomaly_cases = generate_anomaly_test_cases()
    for case in anomaly_cases:
        all_cases.append(case)
    
    # 4. Mixed Data Test Cases (6个)
    mixed_cases = generate_mixed_data_test_cases()
    for case in mixed_cases:
        all_cases.append(case)
    
    # 5. Business Flow Test Cases (6个)
    business_cases = generate_business_flow_test_cases()
    for case in business_cases:
        all_cases.append(case)
    
    # Define unified columns
    columns = [
        "用例ID", "用例名称", "驱动类型", "参数1", "参数2", "参数3",
        "参数4", "参数5", "流量工具", "优先级", "必选/可选", "用例类型", "对应Python文件"
    ]
    
    # Create DataFrame
    df = pd.DataFrame(all_cases, columns=columns)
    
    # Add common columns
    df["状态"] = "active"
    df["负责人"] = ""
    df["最后更新时间"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    df["测试目的"] = "验证网卡稳定性"
    
    # Reorder columns to match expected format
    column_order = [
        "用例ID", "用例名称", "用例类型", "驱动类型", "优先级", "必选/可选",
        "对应Python文件", "测试目的", "参数1", "参数2", "参数3", "参数4", "参数5",
        "流量工具", "状态", "负责人", "最后更新时间"
    ]
    df = df[column_order]
    
    # Save to Excel
    output_path = Path(__file__).parent.parent / "testcase_list.xlsx"
    df.to_excel(output_path, index=False, sheet_name="TestCases")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Generated testcase_list.xlsx with {len(df)} test cases")
    print(f"Location: {output_path}")
    print(f"{'='*60}")
    
    summary = df.groupby("用例类型").size()
    print("\nTest case summary:")
    for test_type, count in summary.items():
        print(f"  {test_type}: {count} cases")
    
    print(f"\nTotal: {len(df)} test cases")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
