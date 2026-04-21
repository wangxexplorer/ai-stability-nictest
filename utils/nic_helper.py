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
        
        exit_code, stdout, stderr = ssh_client.execute(f"ethtool -l {nic_name}")
        if exit_code == 0:
            for line in stdout.split('\n'):
                if 'Combined:' in line:
                    try:
                        config['combined'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
        
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
