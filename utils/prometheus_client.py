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
