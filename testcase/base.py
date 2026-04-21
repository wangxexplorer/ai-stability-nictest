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
            
            self.setup()
            
            self.results = self.run()
            
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
