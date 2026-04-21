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
