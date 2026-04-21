"""Stress test implementations for NIC stability testing."""
import pytest
import time
import subprocess
from typing import Dict, Any, List
from testcase.base import BaseTestCase
from utils.ssh_client import SSHClient
from utils.nic_helper import NICHelper
from utils.prometheus_client import PrometheusClient
import yaml
import logging

logger = logging.getLogger(__name__)


class StressTestConfig:
    """Configuration loader for stress tests."""
    
    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Load test configuration from YAML file."""
        with open('config/test_config.yaml', 'r') as f:
            return yaml.safe_load(f)


class KernelStressTest(BaseTestCase):
    """Kernel driver stress test implementation using iperf3."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.test_config = StressTestConfig.load_config()
        self.ssh_dut = None
        self.ssh_tester = None
        self.iperf3_server_pid = None
        
    def setup(self) -> None:
        """Setup iperf3 server on DUT."""
        dut_config = self.test_config['devices']['dut']
        tester_config = self.test_config['devices']['tester']
        
        self.ssh_dut = SSHClient(
            dut_config['ip'],
            dut_config['user'],
            dut_config['password'],
            dut_config['ssh_port']
        )
        self.ssh_tester = SSHClient(
            tester_config['ip'],
            tester_config['user'],
            tester_config['password'],
            tester_config['ssh_port']
        )
        
        self.ssh_dut.connect()
        self.ssh_tester.connect()
        
        # Start iperf3 server on DUT
        self.ssh_dut.execute("pkill iperf3")
        time.sleep(1)
        _, stdout, _ = self.ssh_dut.execute("iperf3 -s -D -1")
        time.sleep(2)
        
        logger.info(f"Setup complete for test: {self.test_name}")
    
    def run(self) -> Dict[str, Any]:
        """Run stress test with iperf3."""
        duration_seconds = self._parse_duration(self.config.get('duration', '1h'))
        bandwidth_target = self.config.get('bandwidth_target', '80%')
        packet_size = self.config.get('packet_size', '1500')
        protocol = self.config.get('protocol', 'tcp')
        parallel_streams = self.config.get('parallel_streams', 16)
        
        nic_name = self.test_config['nics'][0]['name']
        dut_ip = self.test_config['devices']['dut']['ip']
        
        # Get NIC speed for bandwidth calculation
        nic_info = NICHelper.get_nic_info(self.ssh_dut, nic_name)
        nic_speed_str = nic_info.get('speed', '10000')
        nic_speed_mbps = self._parse_speed(nic_speed_str)
        
        # Calculate target bandwidth
        target_percent = float(bandwidth_target.replace('%', '')) / 100
        target_bandwidth = int(nic_speed_mbps * target_percent)
        
        # Record initial metrics
        initial_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        
        # Build iperf3 command
        if protocol == 'udp':
            iperf_cmd = f"iperf3 -c {dut_ip} -u -b {target_bandwidth}M -l {packet_size} " \
                       f"-P {parallel_streams} -t {duration_seconds} -f m --get-server-output"
        else:
            iperf_cmd = f"iperf3 -c {dut_ip} -b {target_bandwidth}M -M {packet_size} " \
                       f"-P {parallel_streams} -t {duration_seconds} -f m --get-server-output"
        
        logger.info(f"Running: {iperf_cmd}")
        
        # Execute test
        exit_code, stdout, stderr = self.ssh_tester.execute(iperf_cmd, timeout=duration_seconds + 60)
        
        # Parse results
        results = self._parse_iperf3_results(stdout, stderr, duration_seconds)
        results['test_id'] = self.test_id
        results['test_name'] = self.test_name
        results['nic_speed_mbps'] = nic_speed_mbps
        results['target_bandwidth_mbps'] = target_bandwidth
        
        # Get final metrics
        final_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        
        # Calculate error delta
        for key in initial_stats:
            results[f'{key}_delta'] = final_stats[key] - initial_stats[key]
        
        return results
    
    def teardown(self) -> None:
        """Stop iperf3 server and cleanup."""
        try:
            if self.ssh_dut:
                self.ssh_dut.execute("pkill iperf3")
        except Exception as e:
            logger.warning(f"Error during teardown: {e}")
        finally:
            if self.ssh_dut:
                self.ssh_dut.close()
            if self.ssh_tester:
                self.ssh_tester.close()
    
    def validate(self, results: Dict[str, Any]) -> bool:
        """Validate stress test results against thresholds."""
        thresholds = self.test_config['thresholds']
        
        # Check packet loss
        packet_loss = results.get('packet_loss_rate', 0)
        max_loss = float(thresholds['packet_loss_rate'].replace('%', ''))
        if packet_loss > max_loss:
            logger.error(f"Packet loss {packet_loss}% exceeds threshold {max_loss}%")
            return False
        
        # Check bandwidth achievement
        actual_bw = results.get('bandwidth_mbps', 0)
        target_bw = results.get('target_bandwidth_mbps', 1)
        achievement = (actual_bw / target_bw) * 100 if target_bw > 0 else 0
        min_achievement = float(thresholds['bandwidth_achievement'].replace('%', ''))
        if achievement < min_achievement:
            logger.error(f"Bandwidth achievement {achievement:.1f}% below threshold {min_achievement}%")
            return False
        
        # Check NIC errors
        max_errors = thresholds['nic_errors_max']
        error_keys = ['rx_errors_delta', 'tx_errors_delta', 'rx_dropped_delta', 'tx_dropped_delta']
        for key in error_keys:
            if results.get(key, 0) > max_errors:
                logger.error(f"NIC error {key}: {results[key]} exceeds threshold {max_errors}")
                return False
        
        return True
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds."""
        if 'h' in duration_str.lower():
            return int(duration_str.lower().replace('h', '')) * 3600
        elif 'm' in duration_str.lower():
            return int(duration_str.lower().replace('m', '')) * 60
        elif 'd' in duration_str.lower():
            return int(duration_str.lower().replace('d', '')) * 86400
        return int(duration_str)
    
    def _parse_speed(self, speed_str: str) -> int:
        """Parse NIC speed string to Mbps."""
        speed_str = speed_str.lower().replace('mb/s', '').replace('mbps', '').strip()
        if 'g' in speed_str:
            return int(float(speed_str.replace('g', '')) * 1000)
        return int(speed_str)
    
    def _parse_iperf3_results(self, stdout: str, stderr: str, duration: int) -> Dict[str, Any]:
        """Parse iperf3 output to extract metrics."""
        results = {
            'bandwidth_mbps': 0,
            'packet_loss_rate': 0,
            'duration_seconds': duration
        }
        
        # Parse bandwidth from summary line
        for line in stdout.split('\n'):
            if 'sender' in line.lower() or 'receiver' in line.lower():
                # Extract bandwidth value
                parts = line.split()
                for i, part in enumerate(parts):
                    if 'mbytes' in part.lower() or 'mbits' in part.lower():
                        try:
                            results['bandwidth_mbps'] = float(parts[i-1])
                        except (ValueError, IndexError):
                            pass
            
            # Parse UDP loss
            if 'loss' in line.lower() and '%' in line:
                try:
                    loss_str = line.split('(')[1].split('%')[0]
                    results['packet_loss_rate'] = float(loss_str)
                except (ValueError, IndexError):
                    pass
        
        return results


class DPDKStressTest(BaseTestCase):
    """DPDK stress test implementation using pktgen."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.test_config = StressTestConfig.load_config()
        self.ssh_dut = None
        self.ssh_tester = None
        
    def setup(self) -> None:
        """Setup DPDK environment."""
        dut_config = self.test_config['devices']['dut']
        tester_config = self.test_config['devices']['tester']
        
        self.ssh_dut = SSHClient(
            dut_config['ip'],
            dut_config['user'],
            dut_config['password'],
            dut_config['ssh_port']
        )
        self.ssh_tester = SSHClient(
            tester_config['ip'],
            tester_config['user'],
            tester_config['password'],
            tester_config['ssh_port']
        )
        
        self.ssh_dut.connect()
        self.ssh_tester.connect()
        
        # Verify DPDK is configured
        exit_code, _, _ = self.ssh_dut.execute("which pktgen-dpdk")
        if exit_code != 0:
            raise RuntimeError("pktgen-dpdk not found on DUT")
        
        logger.info(f"DPDK setup complete for test: {self.test_name}")
    
    def run(self) -> Dict[str, Any]:
        """Run DPDK stress test with pktgen."""
        duration_seconds = self._parse_duration(self.config.get('duration', '4h'))
        bandwidth_target = self.config.get('bandwidth_target', '80%')
        packet_size = self.config.get('packet_size', '1500')
        parallel_streams = self.config.get('parallel_streams', 16)
        
        nic_name = self.test_config['nics'][0]['name']
        
        # Get initial stats
        initial_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        
        # Build pktgen command
        pktgen_cmd = f"pktgen -l 0-3 -n 4 -- -P -m '[1-3:0].0' " \
                     f"-s 0:{packet_size} -d {duration_seconds}"
        
        logger.info(f"Running DPDK test: {pktgen_cmd}")
        
        # Execute pktgen on tester
        exit_code, stdout, stderr = self.ssh_tester.execute(
            pktgen_cmd, 
            timeout=duration_seconds + 60
        )
        
        # Parse results (pktgen specific output parsing)
        results = {
            'test_id': self.test_id,
            'test_name': self.test_name,
            'bandwidth_mbps': 0,
            'packet_loss_rate': 0,
            'duration_seconds': duration_seconds,
            'stdout': stdout,
            'stderr': stderr
        }
        
        # Parse pktgen output
        for line in stdout.split('\n'):
            if 'Tx' in line and 'pps' in line:
                try:
                    # Extract throughput
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'mbps' in part.lower():
                            results['bandwidth_mbps'] = float(parts[i-1])
                except (ValueError, IndexError):
                    pass
        
        # Get final stats
        final_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        for key in initial_stats:
            results[f'{key}_delta'] = final_stats[key] - initial_stats[key]
        
        return results
    
    def teardown(self) -> None:
        """Cleanup DPDK environment."""
        try:
            if self.ssh_tester:
                self.ssh_tester.execute("pkill pktgen")
        except Exception as e:
            logger.warning(f"Error during DPDK teardown: {e}")
        finally:
            if self.ssh_dut:
                self.ssh_dut.close()
            if self.ssh_tester:
                self.ssh_tester.close()
    
    def validate(self, results: Dict[str, Any]) -> bool:
        """Validate DPDK stress test results."""
        thresholds = self.test_config['thresholds']
        
        # DPDK has stricter requirements
        if results.get('rx_errors_delta', 0) > 0 or results.get('tx_errors_delta', 0) > 0:
            logger.error("NIC errors detected in DPDK test")
            return False
        
        return True
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds."""
        if 'h' in duration_str.lower():
            return int(duration_str.lower().replace('h', '')) * 3600
        elif 'm' in duration_str.lower():
            return int(duration_str.lower().replace('m', '')) * 60
        return int(duration_str)


class RDMAStressTest(BaseTestCase):
    """RDMA stress test implementation using perftest."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.test_config = StressTestConfig.load_config()
        self.ssh_dut = None
        self.ssh_tester = None
        
    def setup(self) -> None:
        """Setup RDMA environment."""
        dut_config = self.test_config['devices']['dut']
        tester_config = self.test_config['devices']['tester']
        
        self.ssh_dut = SSHClient(
            dut_config['ip'],
            dut_config['user'],
            dut_config['password'],
            dut_config['ssh_port']
        )
        self.ssh_tester = SSHClient(
            tester_config['ip'],
            tester_config['user'],
            tester_config['password'],
            tester_config['ssh_port']
        )
        
        self.ssh_dut.connect()
        self.ssh_tester.connect()
        
        # Verify RDMA tools are available
        exit_code, _, _ = self.ssh_dut.execute("which ib_write_bw")
        if exit_code != 0:
            raise RuntimeError("ib_write_bw not found on DUT")
        
        logger.info(f"RDMA setup complete for test: {self.test_name}")
    
    def run(self) -> Dict[str, Any]:
        """Run RDMA stress test with perftest."""
        duration_seconds = self._parse_duration(self.config.get('duration', '1h'))
        test_type = self.config.get('test_type', 'ib_write_bw')
        qp_count = self.config.get('parallel_streams', 256)
        bidirectional = self.config.get('bidirectional', False)
        
        dut_ip = self.test_config['devices']['dut']['ip']
        
        # Start RDMA server on DUT
        server_cmd = f"{test_type} -d mlx5_0 --report_gbit -F &"
        if bidirectional:
            server_cmd = f"{test_type} -d mlx5_0 --report_gbit -F -b &"
        
        self.ssh_dut.execute(server_cmd)
        time.sleep(2)
        
        # Build client command
        client_cmd = f"{test_type} -d mlx5_0 {dut_ip} --report_gbit -F -D {duration_seconds}"
        if bidirectional:
            client_cmd += " -b"
        if qp_count > 1:
            client_cmd += f" -q {qp_count}"
        
        logger.info(f"Running RDMA test: {client_cmd}")
        
        # Execute test
        exit_code, stdout, stderr = self.ssh_tester.execute(
            client_cmd,
            timeout=duration_seconds + 30
        )
        
        # Parse perftest results
        results = {
            'test_id': self.test_id,
            'test_name': self.test_name,
            'bandwidth_gbps': 0,
            'latency_usec': 0,
            'duration_seconds': duration_seconds
        }
        
        for line in stdout.split('\n'):
            if 'bandwidth' in line.lower() and 'gb/sec' in line.lower():
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'gb/sec' in part.lower():
                            results['bandwidth_gbps'] = float(parts[i-1])
                except (ValueError, IndexError):
                    pass
            
            if 'average' in line.lower() and 'usec' in line.lower():
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'usec' in part.lower():
                            results['latency_usec'] = float(parts[i-1])
                except (ValueError, IndexError):
                    pass
        
        return results
    
    def teardown(self) -> None:
        """Cleanup RDMA environment."""
        try:
            if self.ssh_dut:
                self.ssh_dut.execute("pkill ib_write_bw ib_read_bw ib_send_bw ib_write_lat")
        except Exception as e:
            logger.warning(f"Error during RDMA teardown: {e}")
        finally:
            if self.ssh_dut:
                self.ssh_dut.close()
            if self.ssh_tester:
                self.ssh_tester.close()
    
    def validate(self, results: Dict[str, Any]) -> bool:
        """Validate RDMA stress test results."""
        bandwidth = results.get('bandwidth_gbps', 0)
        if bandwidth <= 0:
            logger.error("No RDMA bandwidth measured")
            return False
        return True
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds."""
        if 'h' in duration_str.lower():
            return int(duration_str.lower().replace('h', '')) * 3600
        elif 'm' in duration_str.lower():
            return int(duration_str.lower().replace('m', '')) * 60
        return int(duration_str)


# ============================================================================
# Kernel TCP Stress Tests (8个)
# ============================================================================

@pytest.mark.stress
@pytest.mark.kernel
class TestKernelTCPStress:
    """Kernel TCP stress tests."""
    
    def test_stress_kernel_tcp_baseline_80percent_30min(self):
        """ST-001: Kernel快速基准验证-80%带宽 (30min, 1500B, 1 stream)."""
        config = {
            'test_id': 'ST-001',
            'test_name': 'Kernel快速基准验证-80%带宽',
            'duration': '30m',
            'bandwidth_target': '80%',
            'packet_size': '1500',
            'protocol': 'tcp',
            'parallel_streams': 1
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_standard_80percent_16stream_1h(self):
        """ST-002: Kernel标准压力测试-80%带宽-16流 (1h, 1500B)."""
        config = {
            'test_id': 'ST-002',
            'test_name': 'Kernel标准压力测试-80%带宽-16流',
            'duration': '1h',
            'bandwidth_target': '80%',
            'packet_size': '1500',
            'protocol': 'tcp',
            'parallel_streams': 16
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_high_pressure_90percent_4h(self):
        """ST-003: Kernel高压压力测试-90%带宽 (4h, 1500B, 16 streams)."""
        config = {
            'test_id': 'ST-003',
            'test_name': 'Kernel高压压力测试-90%带宽',
            'duration': '4h',
            'bandwidth_target': '90%',
            'packet_size': '1500',
            'protocol': 'tcp',
            'parallel_streams': 16
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_small_packet_pps_64b_4h(self):
        """ST-004: Kernel小包PPS极限测试-64B (4h, 80%, 32 streams)."""
        config = {
            'test_id': 'ST-004',
            'test_name': 'Kernel小包PPS极限测试-64B',
            'duration': '4h',
            'bandwidth_target': '80%',
            'packet_size': '64',
            'protocol': 'tcp',
            'parallel_streams': 32
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_large_packet_64kb_4h(self):
        """ST-005: Kernel大包带宽测试-64KB (4h, 80%, 8 streams)."""
        config = {
            'test_id': 'ST-005',
            'test_name': 'Kernel大包带宽测试-64KB',
            'duration': '4h',
            'bandwidth_target': '80%',
            'packet_size': '64000',
            'protocol': 'tcp',
            'parallel_streams': 8
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_jumbo_frame_9000b_1h(self):
        """ST-006: Kernel Jumbo Frame测试-9000B (1h, 80%, 8 streams)."""
        config = {
            'test_id': 'ST-006',
            'test_name': 'Kernel Jumbo Frame测试-9000B',
            'duration': '1h',
            'bandwidth_target': '80%',
            'packet_size': '9000',
            'protocol': 'tcp',
            'parallel_streams': 8
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_extreme_95percent_1h(self):
        """ST-007: Kernel极高带宽测试-95% (1h, 1500B, 16 streams)."""
        config = {
            'test_id': 'ST-007',
            'test_name': 'Kernel极高带宽测试-95%',
            'duration': '1h',
            'bandwidth_target': '95%',
            'packet_size': '1500',
            'protocol': 'tcp',
            'parallel_streams': 16
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_tcp_extended_80percent_24h(self):
        """ST-008: Kernel长压力测试-24h (1500B, 8 streams)."""
        config = {
            'test_id': 'ST-008',
            'test_name': 'Kernel长压力测试-24h',
            'duration': '24h',
            'bandwidth_target': '80%',
            'packet_size': '1500',
            'protocol': 'tcp',
            'parallel_streams': 8
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"


# ============================================================================
# Kernel UDP Stress Tests (3个)
# ============================================================================

@pytest.mark.stress
@pytest.mark.kernel
class TestKernelUDPStress:
    """Kernel UDP stress tests."""
    
    def test_stress_kernel_udp_bandwidth_80percent_1h(self):
        """ST-009: Kernel UDP带宽测试-80% (1h, 1500B, 16 streams)."""
        config = {
            'test_id': 'ST-009',
            'test_name': 'Kernel UDP带宽测试-80%',
            'duration': '1h',
            'bandwidth_target': '80%',
            'packet_size': '1500',
            'protocol': 'udp',
            'parallel_streams': 16
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_udp_loss_small_packet_4h(self):
        """ST-010: Kernel UDP丢包测试-小包 (4h, 80%, 64B, 32 streams)."""
        config = {
            'test_id': 'ST-010',
            'test_name': 'Kernel UDP丢包测试-小包',
            'duration': '4h',
            'bandwidth_target': '80%',
            'packet_size': '64',
            'protocol': 'udp',
            'parallel_streams': 32
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_kernel_udp_pps_extreme_64b_4h(self):
        """ST-011: Kernel UDP PPS极限测试-64B高频 (4h, 90%, 64 streams)."""
        config = {
            'test_id': 'ST-011',
            'test_name': 'Kernel UDP PPS极限测试-64B高频',
            'duration': '4h',
            'bandwidth_target': '90%',
            'packet_size': '64',
            'protocol': 'udp',
            'parallel_streams': 64
        }
        test = KernelStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"


# ============================================================================
# DPDK Stress Tests (3个)
# ============================================================================

@pytest.mark.stress
@pytest.mark.dpdk
class TestDPDKStress:
    """DPDK stress tests."""
    
    def test_stress_dpdk_standard_80percent_4h(self):
        """ST-012: DPDK标准压力测试 (4h, 80%, 1500B, 16 streams)."""
        config = {
            'test_id': 'ST-012',
            'test_name': 'DPDK标准压力测试',
            'duration': '4h',
            'bandwidth_target': '80%',
            'packet_size': '1500',
            'parallel_streams': 16
        }
        test = DPDKStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_dpdk_small_packet_pps_64b_4h(self):
        """ST-013: DPDK小包PPS测试 (4h, 80%, 64B, 32 streams)."""
        config = {
            'test_id': 'ST-013',
            'test_name': 'DPDK小包PPS测试',
            'duration': '4h',
            'bandwidth_target': '80%',
            'packet_size': '64',
            'parallel_streams': 32
        }
        test = DPDKStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_dpdk_high_pressure_90percent_1h(self):
        """ST-014: DPDK高压测试-90% (1h, 1500B, 16 streams)."""
        config = {
            'test_id': 'ST-014',
            'test_name': 'DPDK高压测试-90%',
            'duration': '1h',
            'bandwidth_target': '90%',
            'packet_size': '1500',
            'parallel_streams': 16
        }
        test = DPDKStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"


# ============================================================================
# RDMA Stress Tests (4个) - 256 QP, 双向模式
# ============================================================================

@pytest.mark.stress
@pytest.mark.rdma
class TestRDMAStress:
    """RDMA stress tests using perftest with 256 QP and bidirectional mode."""
    
    def test_stress_rdma_write_bw_256qp_bidirectional_1h(self):
        """ST-015: RDMA Write双向带宽测试-256QP (1h, 80%, bidirectional)."""
        config = {
            'test_id': 'ST-015',
            'test_name': 'RDMA Write双向带宽测试-256QP',
            'duration': '1h',
            'bandwidth_target': '80%',
            'test_type': 'ib_write_bw',
            'parallel_streams': 256,
            'bidirectional': True
        }
        test = RDMAStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_rdma_read_bw_256qp_bidirectional_1h(self):
        """ST-016: RDMA Read双向带宽测试-256QP (1h, 80%, bidirectional)."""
        config = {
            'test_id': 'ST-016',
            'test_name': 'RDMA Read双向带宽测试-256QP',
            'duration': '1h',
            'bandwidth_target': '80%',
            'test_type': 'ib_read_bw',
            'parallel_streams': 256,
            'bidirectional': True
        }
        test = RDMAStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_rdma_send_bw_256qp_bidirectional_1h(self):
        """ST-017: RDMA Send双向带宽测试-256QP (1h, 80%, bidirectional)."""
        config = {
            'test_id': 'ST-017',
            'test_name': 'RDMA Send双向带宽测试-256QP',
            'duration': '1h',
            'bandwidth_target': '80%',
            'test_type': 'ib_send_bw',
            'parallel_streams': 256,
            'bidirectional': True
        }
        test = RDMAStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_stress_rdma_write_lat_256qp_30min(self):
        """ST-018: RDMA Write延迟测试-256QP (30min, latency mode)."""
        config = {
            'test_id': 'ST-018',
            'test_name': 'RDMA Write延迟测试-256QP',
            'duration': '30m',
            'bandwidth_target': '-',
            'test_type': 'ib_write_lat',
            'parallel_streams': 256,
            'bidirectional': False
        }
        test = RDMAStressTest(config)
        result = test.execute()
        assert result['passed'], f"Test failed: {result.get('error', 'Unknown error')}"
