"""Longevity test implementations for NIC stability testing."""
import pytest
import time
from typing import Dict, Any, List
from datetime import datetime
from testcase.base import BaseTestCase
from utils.ssh_client import SSHClient
from utils.nic_helper import NICHelper
from utils.prometheus_client import PrometheusClient
from utils.validators import parse_duration, parse_speed, load_test_config
import logging

logger = logging.getLogger(__name__)


class KernelLongevityTest(BaseTestCase):
    """Kernel driver longevity test implementation using iperf3."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.test_config = load_test_config()
        self.ssh_dut = None
        self.ssh_tester = None
        self.prometheus = None
        self.initial_memory = 0.0
        
    def setup(self) -> None:
        """Setup iperf3 server on DUT and initialize Prometheus monitoring."""
        dut_config = self.test_config["devices"]["dut"]
        tester_config = self.test_config["devices"]["tester"]
        monitor_config = self.test_config["devices"]["monitor"]
        
        self.ssh_dut = SSHClient(
            dut_config["ip"],
            dut_config["user"],
            dut_config["password"],
            dut_config["ssh_port"]
        )
        self.ssh_tester = SSHClient(
            tester_config["ip"],
            tester_config["user"],
            tester_config["password"],
            tester_config["ssh_port"]
        )
        
        self.ssh_dut.connect()
        self.ssh_tester.connect()
        
        # Start iperf3 server on DUT
        self.ssh_dut.execute("pkill iperf3")
        time.sleep(1)
        self.ssh_dut.execute("iperf3 -s -D -1")
        time.sleep(2)
        
        # Initialize Prometheus client for memory leak detection
        self.prometheus = PrometheusClient(monitor_config["prometheus_url"])
        try:
            self.initial_memory = self.prometheus.get_memory_usage(dut_config["ip"])
            logger.info(f"Initial memory usage: {self.initial_memory:.2f}%")
        except Exception as e:
            logger.warning(f"Failed to get initial memory usage: {e}")
        
        logger.info(f"Setup complete for longevity test: {self.test_name}")
    
    def run(self) -> Dict[str, Any]:
        """Run longevity test with iperf3."""
        duration_seconds = parse_duration(self.config.get("duration", "168h"))
        bandwidth_target = self.config.get("bandwidth_target", "75%")
        packet_size = self.config.get("packet_size", "1500")
        protocol = self.config.get("protocol", "tcp")
        parallel_streams = self.config.get("parallel_streams", 8)
        traffic_pattern = self.config.get("traffic_pattern", "constant")
        
        nic_name = self.test_config["nics"][0]["name"]
        dut_ip = self.test_config["devices"]["dut"]["ip"]
        
        # Get NIC speed for bandwidth calculation
        nic_info = NICHelper.get_nic_info(self.ssh_dut, nic_name)
        nic_speed_str = nic_info.get("speed", "10000")
        nic_speed_mbps = parse_speed(nic_speed_str)
        
        # Record initial NIC statistics
        initial_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        
        # Execute test based on traffic pattern
        if traffic_pattern == "periodic":
            cycle_duration = self.config.get("cycle_duration", "4h")
            min_bandwidth = self.config.get("min_bandwidth", "50%")
            max_bandwidth = self.config.get("max_bandwidth", "90%")
            results = self._run_periodic_traffic(
                dut_ip, nic_speed_mbps, packet_size, protocol, parallel_streams,
                duration_seconds, cycle_duration, min_bandwidth, max_bandwidth
            )
        else:
            results = self._run_constant_traffic(
                dut_ip, nic_speed_mbps, packet_size, protocol, parallel_streams,
                duration_seconds, bandwidth_target
            )
        
        results["test_id"] = self.test_id
        results["test_name"] = self.test_name
        results["nic_speed_mbps"] = nic_speed_mbps
        results["traffic_pattern"] = traffic_pattern
        
        # Get final NIC statistics
        final_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        for key in initial_stats:
            results[f"{key}_delta"] = final_stats[key] - initial_stats[key]
        
        # Get final memory usage for leak detection
        if self.prometheus:
            try:
                final_memory = self.prometheus.get_memory_usage(
                    self.test_config["devices"]["dut"]["ip"]
                )
                results["memory_before_percent"] = self.initial_memory
                results["memory_after_percent"] = final_memory
                results["memory_growth_percent"] = final_memory - self.initial_memory
                logger.info(
                    f"Final memory usage: {final_memory:.2f}%, "
                    f"growth: {results['memory_growth_percent']:.2f}%"
                )
            except Exception as e:
                logger.warning(f"Failed to get final memory usage: {e}")
        
        return results
    
    def _run_constant_traffic(
        self, dut_ip: str, nic_speed_mbps: int, packet_size: str,
        protocol: str, parallel_streams: int, duration_seconds: int,
        bandwidth_target: str
    ) -> Dict[str, Any]:
        """Run constant traffic longevity test."""
        target_percent = float(bandwidth_target.replace("%", "")) / 100
        target_bandwidth = int(nic_speed_mbps * target_percent)
        
        # Build iperf3 command
        if protocol == "udp":
            iperf_cmd = (
                f"iperf3 -c {dut_ip} -u -b {target_bandwidth}M -l {packet_size} "
                f"-P {parallel_streams} -t {duration_seconds} -f m --get-server-output"
            )
        else:
            iperf_cmd = (
                f"iperf3 -c {dut_ip} -b {target_bandwidth}M -M {packet_size} "
                f"-P {parallel_streams} -t {duration_seconds} -f m --get-server-output"
            )
        
        logger.info(f"Running constant longevity test: {iperf_cmd}")
        
        exit_code, stdout, stderr = self.ssh_tester.execute(
            iperf_cmd,
            timeout=duration_seconds + 60
        )
        
        results = self._parse_iperf3_results(stdout, stderr, duration_seconds)
        results["target_bandwidth_mbps"] = target_bandwidth
        
        return results
    
    def _run_periodic_traffic(
        self, dut_ip: str, nic_speed_mbps: int, packet_size: str,
        protocol: str, parallel_streams: int, duration_seconds: int,
        cycle_duration: str, min_bandwidth: str, max_bandwidth: str
    ) -> Dict[str, Any]:
        """Run periodic fluctuating traffic longevity test."""
        cycle_seconds = parse_duration(cycle_duration)
        num_cycles = duration_seconds // cycle_seconds
        remaining_time = duration_seconds % cycle_seconds
        
        min_bw_percent = float(min_bandwidth.replace("%", "")) / 100
        max_bw_percent = float(max_bandwidth.replace("%", "")) / 100
        
        logger.info(
            f"Periodic traffic: {num_cycles} cycles of {cycle_seconds}s, "
            f"bandwidth range: {min_bw_percent * 100:.0f}%-{max_bw_percent * 100:.0f}%"
        )
        
        all_bandwidths: List[float] = []
        all_loss_rates: List[float] = []
        
        for cycle in range(num_cycles):
            half_cycle = cycle_seconds // 2
            
            for bw_percent in [min_bw_percent, max_bw_percent]:
                target_bandwidth = int(nic_speed_mbps * bw_percent)
                
                if protocol == "udp":
                    iperf_cmd = (
                        f"iperf3 -c {dut_ip} -u -b {target_bandwidth}M -l {packet_size} "
                        f"-P {parallel_streams} -t {half_cycle} -f m --get-server-output"
                    )
                else:
                    iperf_cmd = (
                        f"iperf3 -c {dut_ip} -b {target_bandwidth}M -M {packet_size} "
                        f"-P {parallel_streams} -t {half_cycle} -f m --get-server-output"
                    )
                
                logger.info(
                    f"Cycle {cycle + 1}/{num_cycles}, "
                    f"bandwidth: {bw_percent * 100:.0f}%"
                )
                
                exit_code, stdout, stderr = self.ssh_tester.execute(
                    iperf_cmd,
                    timeout=half_cycle + 60
                )
                
                cycle_results = self._parse_iperf3_results(stdout, stderr, half_cycle)
                all_bandwidths.append(cycle_results.get("bandwidth_mbps", 0))
                all_loss_rates.append(cycle_results.get("packet_loss_rate", 0))
        
        # Handle remaining time with average bandwidth
        if remaining_time > 0:
            avg_percent = (min_bw_percent + max_bw_percent) / 2
            target_bandwidth = int(nic_speed_mbps * avg_percent)
            
            if protocol == "udp":
                iperf_cmd = (
                    f"iperf3 -c {dut_ip} -u -b {target_bandwidth}M -l {packet_size} "
                    f"-P {parallel_streams} -t {remaining_time} -f m --get-server-output"
                )
            else:
                iperf_cmd = (
                    f"iperf3 -c {dut_ip} -b {target_bandwidth}M -M {packet_size} "
                    f"-P {parallel_streams} -t {remaining_time} -f m --get-server-output"
                )
            
            logger.info(
                f"Final segment: {remaining_time}s at "
                f"{avg_percent * 100:.0f}% bandwidth"
            )
            
            exit_code, stdout, stderr = self.ssh_tester.execute(
                iperf_cmd,
                timeout=remaining_time + 60
            )
            
            cycle_results = self._parse_iperf3_results(stdout, stderr, remaining_time)
            all_bandwidths.append(cycle_results.get("bandwidth_mbps", 0))
            all_loss_rates.append(cycle_results.get("packet_loss_rate", 0))
        
        # Aggregate results
        avg_bandwidth = sum(all_bandwidths) / len(all_bandwidths) if all_bandwidths else 0
        min_bw = min(all_bandwidths) if all_bandwidths else 0
        max_bw = max(all_bandwidths) if all_bandwidths else 0
        avg_loss_rate = sum(all_loss_rates) / len(all_loss_rates) if all_loss_rates else 0
        
        return {
            "bandwidth_mbps": avg_bandwidth,
            "bandwidth_min_mbps": min_bw,
            "bandwidth_max_mbps": max_bw,
            "duration_seconds": duration_seconds,
            "packet_loss_rate": avg_loss_rate,
            "cycle_count": num_cycles,
            "target_bandwidth_mbps": int(nic_speed_mbps * ((min_bw_percent + max_bw_percent) / 2))
        }
    
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
        """Validate longevity test results against thresholds."""
        thresholds = self.test_config["thresholds"]
        
        # Check packet loss
        packet_loss = results.get("packet_loss_rate", 0)
        max_loss = float(thresholds["packet_loss_rate"].replace("%", ""))
        if packet_loss > max_loss:
            logger.error(
                f"Packet loss {packet_loss}% exceeds threshold {max_loss}%"
            )
            return False
        
        # Check bandwidth achievement
        actual_bw = results.get("bandwidth_mbps", 0)
        target_bw = results.get("target_bandwidth_mbps", 1)
        if target_bw > 0:
            achievement = (actual_bw / target_bw) * 100
            min_achievement = float(
                thresholds["bandwidth_achievement"].replace("%", "")
            )
            if achievement < min_achievement:
                logger.error(
                    f"Bandwidth achievement {achievement:.1f}% below "
                    f"threshold {min_achievement}%"
                )
                return False
        
        # Check NIC errors
        max_errors = thresholds["nic_errors_max"]
        error_keys = [
            "rx_errors_delta", "tx_errors_delta",
            "rx_dropped_delta", "tx_dropped_delta"
        ]
        for key in error_keys:
            if results.get(key, 0) > max_errors:
                logger.error(
                    f"NIC error {key}: {results[key]} exceeds "
                    f"threshold {max_errors}"
                )
                return False
        
        # Check memory leak
        memory_growth = results.get("memory_growth_percent")
        if memory_growth is not None:
            max_growth = float(thresholds["memory_growth_max"].replace("%", ""))
            if memory_growth > max_growth:
                logger.error(
                    f"Memory growth {memory_growth:.2f}% exceeds "
                    f"threshold {max_growth}%"
                )
                return False
        
        return True
    
    def _parse_iperf3_results(self, stdout: str, stderr: str, duration: int) -> Dict[str, Any]:
        """Parse iperf3 output to extract metrics."""
        results = {
            "bandwidth_mbps": 0,
            "packet_loss_rate": 0,
            "duration_seconds": duration
        }
        
        for line in stdout.split("\n"):
            if "sender" in line.lower() or "receiver" in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if "mbytes" in part.lower() or "mbits" in part.lower():
                        try:
                            results["bandwidth_mbps"] = float(parts[i - 1])
                        except (ValueError, IndexError):
                            pass
            
            if "loss" in line.lower() and "%" in line:
                try:
                    loss_str = line.split("(")[1].split("%")[0]
                    results["packet_loss_rate"] = float(loss_str)
                except (ValueError, IndexError):
                    pass
        
        return results


# ============================================================================
# Kernel TCP Longevity Tests (4个)
# ============================================================================


class DPDKLongevityTest(BaseTestCase):
    """DPDK longevity test implementation using pktgen."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.test_config = load_test_config()
        self.ssh_dut = None
        self.ssh_tester = None
        self.prometheus = None
        self.initial_memory = 0.0
        
    def setup(self) -> None:
        """Setup DPDK environment and initialize Prometheus monitoring."""
        dut_config = self.test_config["devices"]["dut"]
        tester_config = self.test_config["devices"]["tester"]
        monitor_config = self.test_config["devices"]["monitor"]
        
        self.ssh_dut = SSHClient(
            dut_config["ip"],
            dut_config["user"],
            dut_config["password"],
            dut_config["ssh_port"]
        )
        self.ssh_tester = SSHClient(
            tester_config["ip"],
            tester_config["user"],
            tester_config["password"],
            tester_config["ssh_port"]
        )
        
        self.ssh_dut.connect()
        self.ssh_tester.connect()
        
        # Verify DPDK is configured
        exit_code, _, _ = self.ssh_dut.execute("which pktgen-dpdk")
        if exit_code != 0:
            raise RuntimeError("pktgen-dpdk not found on DUT")
        
        # Initialize Prometheus client for memory leak detection
        self.prometheus = PrometheusClient(monitor_config["prometheus_url"])
        try:
            self.initial_memory = self.prometheus.get_memory_usage(dut_config["ip"])
            logger.info(f"Initial memory usage: {self.initial_memory:.2f}%")
        except Exception as e:
            logger.warning(f"Failed to get initial memory usage: {e}")
        
        logger.info(f"DPDK setup complete for longevity test: {self.test_name}")
    
    def run(self) -> Dict[str, Any]:
        """Run DPDK longevity test with pktgen."""
        duration_seconds = parse_duration(self.config.get("duration", "168h"))
        bandwidth_target = self.config.get("bandwidth_target", "75%")
        packet_size = self.config.get("packet_size", "1500")
        parallel_streams = self.config.get("parallel_streams", 8)
        
        nic_name = self.test_config["nics"][0]["name"]
        
        # Calculate target bandwidth from percentage
        nic_info = NICHelper.get_nic_info(self.ssh_dut, nic_name)
        nic_speed_str = nic_info.get("speed", "10000")
        nic_speed_mbps = parse_speed(nic_speed_str)
        target_percent = float(bandwidth_target.replace("%", "")) / 100
        target_bandwidth_mbps = int(nic_speed_mbps * target_percent)
        
        # Get initial stats
        initial_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        
        # Build pktgen command with calculated bandwidth rate
        target_rate_percent = int(target_percent * 100)
        pktgen_cmd = (
            f"pktgen -l 0-3 -n 4 -- -P -m '[1-3:0].0' "
            f"-s 0:{packet_size} -d {duration_seconds} "
            f"-r {target_rate_percent}%"
        )
        
        logger.info(f"Running DPDK longevity test: {pktgen_cmd}")
        
        # Execute pktgen on tester
        exit_code, stdout, stderr = self.ssh_tester.execute(
            pktgen_cmd,
            timeout=duration_seconds + 60
        )
        
        # Parse results (pktgen specific output parsing)
        results = {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "target_bandwidth_mbps": target_bandwidth_mbps,
            "nic_speed_mbps": nic_speed_mbps,
            "bandwidth_mbps": 0,
            "packet_loss_rate": 0,
            "duration_seconds": duration_seconds,
            "stdout": stdout,
            "stderr": stderr
        }
        
        # Parse pktgen output
        for line in stdout.split("\n"):
            if "Tx" in line and "pps" in line:
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "mbps" in part.lower():
                            results["bandwidth_mbps"] = float(parts[i - 1])
                except (ValueError, IndexError):
                    pass
        
        # Get final stats
        final_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        for key in initial_stats:
            results[f"{key}_delta"] = final_stats[key] - initial_stats[key]
        
        # Get final memory usage for leak detection
        if self.prometheus:
            try:
                final_memory = self.prometheus.get_memory_usage(
                    self.test_config["devices"]["dut"]["ip"]
                )
                results["memory_before_percent"] = self.initial_memory
                results["memory_after_percent"] = final_memory
                results["memory_growth_percent"] = final_memory - self.initial_memory
                logger.info(
                    f"Final memory usage: {final_memory:.2f}%, "
                    f"growth: {results['memory_growth_percent']:.2f}%"
                )
            except Exception as e:
                logger.warning(f"Failed to get final memory usage: {e}")
        
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
        """Validate DPDK longevity test results."""
        thresholds = self.test_config["thresholds"]
        
        # DPDK has stricter requirements - zero NIC errors
        if results.get("rx_errors_delta", 0) > 0 or results.get("tx_errors_delta", 0) > 0:
            logger.error("NIC errors detected in DPDK longevity test")
            return False
        
        # Check memory leak
        memory_growth = results.get("memory_growth_percent")
        if memory_growth is not None:
            max_growth = float(thresholds["memory_growth_max"].replace("%", ""))
            if memory_growth > max_growth:
                logger.error(
                    f"Memory growth {memory_growth:.2f}% exceeds "
                    f"threshold {max_growth}%"
                )
                return False
        
        return True


class RDMALongevityTest(BaseTestCase):
    """RDMA longevity test implementation using perftest."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.test_config = load_test_config()
        self.ssh_dut = None
        self.ssh_tester = None
        self.prometheus = None
        self.initial_memory = 0.0
        
    def setup(self) -> None:
        """Setup RDMA environment and initialize Prometheus monitoring."""
        dut_config = self.test_config["devices"]["dut"]
        tester_config = self.test_config["devices"]["tester"]
        monitor_config = self.test_config["devices"]["monitor"]
        
        self.ssh_dut = SSHClient(
            dut_config["ip"],
            dut_config["user"],
            dut_config["password"],
            dut_config["ssh_port"]
        )
        self.ssh_tester = SSHClient(
            tester_config["ip"],
            tester_config["user"],
            tester_config["password"],
            tester_config["ssh_port"]
        )
        
        self.ssh_dut.connect()
        self.ssh_tester.connect()
        
        # Verify RDMA tools are available
        exit_code, _, _ = self.ssh_dut.execute("which ib_write_bw")
        if exit_code != 0:
            raise RuntimeError("ib_write_bw not found on DUT")
        
        # Initialize Prometheus client for memory leak detection
        self.prometheus = PrometheusClient(monitor_config["prometheus_url"])
        try:
            self.initial_memory = self.prometheus.get_memory_usage(dut_config["ip"])
            logger.info(f"Initial memory usage: {self.initial_memory:.2f}%")
        except Exception as e:
            logger.warning(f"Failed to get initial memory usage: {e}")
        
        logger.info(f"RDMA setup complete for longevity test: {self.test_name}")
    
    def run(self) -> Dict[str, Any]:
        """Run RDMA longevity test with perftest."""
        duration_seconds = parse_duration(self.config.get("duration", "168h"))
        test_type = self.config.get("test_type", "ib_write_bw")
        qp_count = self.config.get("parallel_streams", 1)
        bidirectional = self.config.get("bidirectional", False)
        
        nic_name = self.test_config["nics"][0]["name"]
        dut_ip = self.test_config["devices"]["dut"]["ip"]
        
        # Get NIC speed for bandwidth achievement validation
        nic_info = NICHelper.get_nic_info(self.ssh_dut, nic_name)
        nic_speed_str = nic_info.get("speed", "10000")
        nic_speed_mbps = parse_speed(nic_speed_str)
        
        # Get initial NIC statistics
        initial_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        
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
        
        logger.info(f"Running RDMA longevity test: {client_cmd}")
        
        # Execute test
        exit_code, stdout, stderr = self.ssh_tester.execute(
            client_cmd,
            timeout=duration_seconds + 30
        )
        
        # Parse perftest results
        results = {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "nic_speed_mbps": nic_speed_mbps,
            "bandwidth_gbps": 0,
            "latency_usec": 0,
            "duration_seconds": duration_seconds
        }
        
        for line in stdout.split("\n"):
            if "bandwidth" in line.lower() and "gb/sec" in line.lower():
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "gb/sec" in part.lower():
                            results["bandwidth_gbps"] = float(parts[i - 1])
                except (ValueError, IndexError):
                    pass
            
            if "average" in line.lower() and "usec" in line.lower():
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "usec" in part.lower():
                            results["latency_usec"] = float(parts[i - 1])
                except (ValueError, IndexError):
                    pass
        
        # Get final NIC statistics
        final_stats = NICHelper.get_nic_statistics(self.ssh_dut, nic_name)
        for key in initial_stats:
            results[f"{key}_delta"] = final_stats[key] - initial_stats[key]
        
        # Get final memory usage for leak detection
        if self.prometheus:
            try:
                final_memory = self.prometheus.get_memory_usage(
                    self.test_config["devices"]["dut"]["ip"]
                )
                results["memory_before_percent"] = self.initial_memory
                results["memory_after_percent"] = final_memory
                results["memory_growth_percent"] = final_memory - self.initial_memory
                logger.info(
                    f"Final memory usage: {final_memory:.2f}%, "
                    f"growth: {results['memory_growth_percent']:.2f}%"
                )
            except Exception as e:
                logger.warning(f"Failed to get final memory usage: {e}")
        
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
        """Validate RDMA longevity test results."""
        thresholds = self.test_config["thresholds"]
        
        bandwidth = results.get("bandwidth_gbps", 0)
        if bandwidth <= 0:
            logger.error("No RDMA bandwidth measured")
            return False
        
        # Check bandwidth achievement
        nic_speed_mbps = results.get("nic_speed_mbps", 0)
        if nic_speed_mbps > 0:
            nic_speed_gbps = nic_speed_mbps / 1000
            achievement = (bandwidth / nic_speed_gbps) * 100
            min_achievement = float(
                thresholds["bandwidth_achievement"].replace("%", "")
            )
            if achievement < min_achievement:
                logger.error(
                    f"RDMA bandwidth achievement {achievement:.1f}% below "
                    f"threshold {min_achievement}%"
                )
                return False
        
        # Check NIC errors (RDMA expects zero errors)
        error_keys = [
            "rx_errors_delta", "tx_errors_delta",
            "rx_dropped_delta", "tx_dropped_delta"
        ]
        for key in error_keys:
            if results.get(key, 0) > 0:
                logger.error(
                    f"NIC error {key}: {results[key]} in RDMA longevity test"
                )
                return False
        
        # Check memory leak
        memory_growth = results.get("memory_growth_percent")
        if memory_growth is not None:
            max_growth = float(thresholds["memory_growth_max"].replace("%", ""))
            if memory_growth > max_growth:
                logger.error(
                    f"Memory growth {memory_growth:.2f}% exceeds "
                    f"threshold {max_growth}%"
                )
                return False
        
        return True


@pytest.mark.longevity
@pytest.mark.kernel
class TestKernelLongevity:
    """Kernel TCP longevity tests."""
    
    def test_longevity_kernel_tcp_24h_75percent(self):
        """LT-001: Kernel快速长时测试-24h (24h, 75%, 1500B, TCP, 8 streams, constant)."""
        config = {
            "test_id": "LT-001",
            "test_name": "Kernel快速长时测试-24h",
            "duration": "24h",
            "bandwidth_target": "75%",
            "packet_size": "1500",
            "protocol": "tcp",
            "parallel_streams": 8,
            "traffic_pattern": "constant"
        }
        test = KernelLongevityTest(config)
        result = test.execute()
        assert result["passed"], f"Test failed: {result.get('error', 'Unknown error')}"
    
    def test_longevity_kernel_tcp_7x24h_75percent(self):
        """LT-002: Kernel标准长时测试-7x24h (168h, 75%, 1500B, TCP, 8 streams, constant)."""
        config = {
            "test_id": "LT-002",
            "test_name": "Kernel标准长时测试-7x24h",
            "duration": "168h",
            "bandwidth_target": "75%",
            "packet_size": "1500",
            "protocol": "tcp",
            "parallel_streams": 8,
            "traffic_pattern": "constant"
        }
        test = KernelLongevityTest(config)
        result = test.execute()
        assert result["passed"], f"Test failed: {result.get('error', 'Unknown error')}"
    
    @pytest.mark.p2
    def test_longevity_kernel_tcp_15days_75percent(self):
        """LT-003: Kernel深度长时测试-15天 (360h, 75%, 1500B, TCP, 8 streams, constant, P2)."""
        config = {
            "test_id": "LT-003",
            "test_name": "Kernel深度长时测试-15天",
            "duration": "360h",
            "bandwidth_target": "75%",
            "packet_size": "1500",
            "protocol": "tcp",
            "parallel_streams": 8,
            "traffic_pattern": "constant"
        }
        test = KernelLongevityTest(config)
        result = test.execute()
        assert result["passed"], f"Test failed: {result.get('error', 'Unknown error')}"
    
    @pytest.mark.p2
    def test_longevity_kernel_tcp_periodic_7x24h(self):
        """LT-006: Kernel周期波动流量测试 (168h, 50%~90%波动, TCP, 8 streams, periodic, P2)."""
        config = {
            "test_id": "LT-006",
            "test_name": "Kernel周期波动流量测试",
            "duration": "168h",
            "bandwidth_target": "75%",
            "packet_size": "1500",
            "protocol": "tcp",
            "parallel_streams": 8,
            "traffic_pattern": "periodic",
            "cycle_duration": "4h",
            "min_bandwidth": "50%",
            "max_bandwidth": "90%"
        }
        test = KernelLongevityTest(config)
        result = test.execute()
        assert result["passed"], f"Test failed: {result.get('error', 'Unknown error')}"


# ============================================================================
# DPDK Longevity Tests (1个)
# ============================================================================

@pytest.mark.longevity
@pytest.mark.dpdk
class TestDPDKLongevity:
    """DPDK longevity tests."""
    
    def test_longevity_dpdk_7x24h_75percent(self):
        """LT-004: DPDK标准长时测试-7x24h (168h, 75%, 1500B, 8 streams, constant)."""
        config = {
            "test_id": "LT-004",
            "test_name": "DPDK标准长时测试-7x24h",
            "duration": "168h",
            "bandwidth_target": "75%",
            "packet_size": "1500",
            "parallel_streams": 8
        }
        test = DPDKLongevityTest(config)
        result = test.execute()
        assert result["passed"], f"Test failed: {result.get('error', 'Unknown error')}"


# ============================================================================
# RDMA Longevity Tests (1个)
# ============================================================================

@pytest.mark.longevity
@pytest.mark.rdma
class TestRDMALongevity:
    """RDMA longevity tests."""
    
    def test_longevity_rdma_write_bw_7x24h(self):
        """LT-005: RDMA标准长时测试-7x24h (168h, 75%, ib_write_bw, 1 stream, constant)."""
        config = {
            "test_id": "LT-005",
            "test_name": "RDMA标准长时测试-7x24h",
            "duration": "168h",
            "bandwidth_target": "75%",
            "test_type": "ib_write_bw",
            "parallel_streams": 1,
            "bidirectional": False
        }
        test = RDMALongevityTest(config)
        result = test.execute()
        assert result["passed"], f"Test failed: {result.get('error', 'Unknown error')}"